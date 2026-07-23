"""The Professional Scanning Sequence, executed.

`analyze(snapshot, window)` runs the 9-step decision template from Lesson 1
section 17 and returns a Verdict. Each step appends to `evidence` so the output
explains *why*, not just *what* (the product's core differentiator).
"""
from __future__ import annotations

import math
from typing import List, Optional

from . import classify, pcr
from .models import (
    Bias,
    ChainSnapshot,
    Invalidation,
    PCRScorecard,
    PositionType,
    StrikeClassification,
    Verdict,
)
from .strategy import suggest

# Weights for the final bias score (must sum to 1.0).
_W_PREMIUM = 0.30
_W_CHGPCR = 0.30
_W_CLASS = 0.25
_W_CONVERSION = 0.15

# Confidence below this => No Trade.
_NO_TRADE_CONFIDENCE = 0.35
# If directional sub-signals actively conflict beyond this, force No Trade.
_CONFLICT_THRESHOLD = 0.55


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _window_rows(snap: ChainSnapshot, atm: float, interval: float, n: int):
    lo, hi = atm - n * interval, atm + n * interval
    return [r for r in snap.sorted_rows() if lo - 1e-6 <= r.strike <= hi + 1e-6]


def analyze(snap: ChainSnapshot, window: int = 3) -> Verdict:
    evidence: List[str] = []
    interval = snap.infer_strike_interval()

    # -- Step 1: Spot & ATM -------------------------------------------------
    atm = snap.atm_strike()
    evidence.append(f"[1] Spot {snap.spot} -> nearest ATM strike {int(atm)} "
                    f"(strike interval {int(interval)}).")

    win = _window_rows(snap, atm, interval, window)

    # -- Step 2: Premium direction -----------------------------------------
    ce_prem = _mean([r.call.premium_change for r in win])
    pe_prem = _mean([r.put.premium_change for r in win])
    if ce_prem > 0 and pe_prem < 0:
        prem_dir, prem_signal = "bullish (Calls rising, Puts falling)", 1.0
    elif ce_prem < 0 and pe_prem > 0:
        prem_dir, prem_signal = "bearish (Calls falling, Puts rising)", -1.0
    else:
        prem_dir, prem_signal = "mixed", 0.0
    evidence.append(f"[2] Premium direction around ATM: {prem_dir} "
                    f"(avg CE {ce_prem:+.2f}, avg PE {pe_prem:+.2f}).")

    # -- Step 3: Top OI zones ----------------------------------------------
    resistance_row = max(snap.rows, key=lambda r: r.call.oi, default=None)
    support_row = max(snap.rows, key=lambda r: r.put.oi, default=None)
    resistance_strike = resistance_row.strike if resistance_row else None
    # Primary support = strongest PUT WRITING at or below ATM (what price must hold).
    put_writers = [
        r for r in snap.sorted_rows()
        if r.strike <= atm + interval
        and classify.classify_put(r.put.premium_change, r.put.change_oi) == PositionType.PUT_WRITING
    ]
    support_strike = (max(put_writers, key=lambda r: r.put.change_oi).strike
                      if put_writers else (support_row.strike if support_row else None))
    evidence.append(f"[3] Highest Call OI (resistance candidate) {int(resistance_strike) if resistance_strike else 'n/a'}; "
                    f"strongest Put support {int(support_strike) if support_strike else 'n/a'}.")

    # -- Step 4: Classify Change in OI -------------------------------------
    classifications: List[StrikeClassification] = []
    class_scores: List[float] = []
    for r in snap.sorted_rows():
        ct = classify.classify_call(r.call.premium_change, r.call.change_oi)
        pt = classify.classify_put(r.put.premium_change, r.put.change_oi)
        sc = StrikeClassification(
            strike=r.strike,
            call_type=ct,
            put_type=pt,
            is_support=(support_strike is not None and abs(r.strike - support_strike) < 1e-6),
            is_resistance=(resistance_strike is not None and abs(r.strike - resistance_strike) < 1e-6),
        )
        # Flag the doc's "far-OTM call with tiny premium rise but big OI" nuance.
        if ct == PositionType.CALL_LONG_BUILDUP and r.strike > atm and r.call.change_oi > 0:
            conv = pcr.oi_to_volume(r.call.change_oi, r.call.volume)
            if r.call.premium_change < 0.25 * interval:
                sc.notes.append("Small premium rise vs large OI add: watch as resistance wall.")
        classifications.append(sc)
        if lo_hi_in_window(r.strike, atm, interval, window):
            class_scores.append(classify.bias_weight(ct))
            class_scores.append(classify.bias_weight(pt))
    class_signal = _clamp(_mean(class_scores), -1.0, 1.0)
    evidence.append(f"[4] Change-in-OI classification computed for {len(classifications)} strikes; "
                    f"net near-ATM classification signal {class_signal:+.2f}.")

    # -- Step 5: PCR scorecards (at ATM row) -------------------------------
    atm_row = snap.row_at(atm)
    card = _pcr_at(atm_row)
    chgpcr = card.change_oi_pcr
    if chgpcr is None or chgpcr <= 0:
        chgpcr_signal = 0.0
        chgpcr_txt = "n/a"
    else:
        # log2(pcr): pcr>1 bullish (put writing dominates fresh adds), <1 bearish.
        chgpcr_signal = _clamp(math.log2(chgpcr), -1.0, 1.0)
        chgpcr_txt = f"{chgpcr:.2f}"
    evidence.append(f"[5] PCR at ATM -> Total {_fmt(card.total_oi_pcr)}, "
                    f"Change-in-OI {chgpcr_txt}, Volume {_fmt(card.volume_pcr)}.")

    # -- Step 6: Volume conversion -----------------------------------------
    ce_conv = card.ce_oi_to_volume
    pe_conv = card.pe_oi_to_volume
    if ce_conv is not None and pe_conv is not None:
        conv_signal = _clamp((pe_conv - ce_conv) / max(pe_conv + ce_conv, 1e-9), -1.0, 1.0)
    else:
        conv_signal = 0.0
    evidence.append(f"[6] OI-to-Volume conversion at ATM -> "
                    f"CE {_pct(ce_conv)}, PE {_pct(pe_conv)} "
                    f"({'Put' if conv_signal > 0 else 'Call'} side conviction stronger).")

    # -- Step 7: Support/Resistance confirmation ---------------------------
    agree = _signals_agree(prem_signal, chgpcr_signal, class_signal, conv_signal)
    evidence.append(f"[7] Signal agreement: {'strong' if agree else 'partial/mixed'} "
                    "(accept S/R only when premium, OI class, PCR and conversion align).")

    # -- Bias & confidence -------------------------------------------------
    score = (_W_PREMIUM * prem_signal + _W_CHGPCR * chgpcr_signal
             + _W_CLASS * class_signal + _W_CONVERSION * conv_signal)
    signals = [prem_signal, chgpcr_signal, class_signal, conv_signal]
    pos = sum(1 for s in signals if s > 0.05)
    neg = sum(1 for s in signals if s < -0.05)
    conflicted = pos > 0 and neg > 0 and abs(score) < _CONFLICT_THRESHOLD * 0.5

    confidence = _clamp(abs(score), 0.0, 1.0)
    if conflicted or confidence < _NO_TRADE_CONFIDENCE:
        bias = Bias.NO_TRADE
    elif score > 0:
        bias = Bias.BULLISH
    else:
        bias = Bias.BEARISH

    # -- Step 8: Strategy selection ----------------------------------------
    strategies = suggest(bias, confidence, atm, support_strike, resistance_strike, interval)
    evidence.append(f"[8] Bias {bias.value} (confidence {confidence:.0%}); "
                    f"{len(strategies)} strategy option(s) suggested.")

    # -- Step 9: Invalidation ----------------------------------------------
    invalidation = _invalidation(bias, support_strike, resistance_strike)
    if invalidation:
        evidence.append(f"[9] Invalidation: {invalidation.condition}")
    else:
        evidence.append("[9] No directional trade -> invalidation not applicable.")

    return Verdict(
        underlying=snap.underlying,
        spot=snap.spot,
        atm=atm,
        expiry=snap.expiry,
        bias=bias,
        confidence=confidence,
        premium_direction=prem_dir,
        support_strike=support_strike,
        resistance_strike=resistance_strike,
        pcr=card,
        classifications=classifications,
        strategies=strategies,
        invalidation=invalidation,
        evidence=evidence,
        timestamp=snap.timestamp,
    )


# ---- helpers ---------------------------------------------------------------


def _pcr_at(row) -> PCRScorecard:
    if row is None:
        return PCRScorecard(None, None, None, None, None)
    return PCRScorecard(
        total_oi_pcr=pcr.total_oi_pcr(row.put.oi, row.call.oi),
        change_oi_pcr=pcr.change_oi_pcr(row.put.change_oi, row.call.change_oi),
        volume_pcr=pcr.volume_pcr(row.put.volume, row.call.volume),
        ce_oi_to_volume=pcr.oi_to_volume(row.call.change_oi, row.call.volume),
        pe_oi_to_volume=pcr.oi_to_volume(row.put.change_oi, row.put.volume),
    )


def _invalidation(bias: Bias, support: Optional[float], resistance: Optional[float]) -> Optional[Invalidation]:
    if bias == Bias.BULLISH and support is not None:
        return Invalidation(
            direction="below",
            level=support,
            condition=(f"Close below {int(support)} with Put OI unwinding and Put premium "
                       "rising -> bullish structure weakens; reassess."),
        )
    if bias == Bias.BEARISH and resistance is not None:
        return Invalidation(
            direction="above",
            level=resistance,
            condition=(f"Close above {int(resistance)} with Call OI unwinding and Call premium "
                       "rising -> bearish structure weakens; reassess."),
        )
    return None


def _signals_agree(*signals: float) -> bool:
    nonzero = [s for s in signals if abs(s) > 0.05]
    if not nonzero:
        return False
    return all(s > 0 for s in nonzero) or all(s < 0 for s in nonzero)


def lo_hi_in_window(strike: float, atm: float, interval: float, n: int) -> bool:
    return atm - n * interval - 1e-6 <= strike <= atm + n * interval + 1e-6


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _fmt(x: Optional[float]) -> str:
    return f"{x:.2f}" if x is not None else "n/a"


def _pct(x: Optional[float]) -> str:
    return f"{x * 100:.1f}%" if x is not None else "n/a"

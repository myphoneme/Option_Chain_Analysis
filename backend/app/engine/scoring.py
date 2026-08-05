"""Weighted multi-factor scoring model.

Replaces the brittle single-rule (ΔPCR-only) direction with a blend of nine
factors. Each factor returns a score in [-1, +1] (positive = bullish) plus a
human note. The composite is the weighted mean over *available* factors, so a
missing input dilutes coverage instead of dragging the result toward zero.

    Structural Bias    12%   (daily bars — context)
    Tactical Bias      13%   (intraday 5-min bars — what you actually trade)
    OI Analysis        20%   (walls + premium/OI writing-vs-buying matrix)
    Change in OI       15%
    PCR                10%
    VWAP               10%
    Volume              5%
    IV                  5%
    Delta/Gamma         5%
    RSI/Momentum        5%
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional

from . import blackscholes as bs
from .indicators import market_structure, momentum, volume_confirmation
from .models import FactorScore

WEIGHTS: Dict[str, float] = {
    # The audit found a 10-day daily structure can contradict the 5-minute chart
    # a trader is watching, so the old single 25% "Market Structure" is split.
    "Structural Bias": 0.12,      # daily bars — context
    "Tactical Bias": 0.13,        # intraday 5-min bars — what you trade
    "OI Analysis": 0.20,
    "Change in OI": 0.15,
    "PCR": 0.10,
    "VWAP": 0.10,
    "Volume": 0.05,
    "IV": 0.05,
    "Delta/Gamma": 0.05,
    "RSI/Momentum": 0.05,
}

# Composite thresholds for a directional call.
DIRECTION_BAND = 0.15
# A strike counts as "liquid" if both legs carry this share of the window's max OI.
_LIQUID_SHARE = 0.05


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def _tanh_ratio(ratio: Optional[float], scale: float = 1.0) -> Optional[float]:
    """Map a put/call ratio to [-1,1]: 1.0 -> 0, >1 bullish, <1 bearish."""
    if not ratio or ratio <= 0:
        return None
    return _clip(math.tanh(math.log(ratio) / scale))


def _liquid_rows(rows):
    """Strikes where BOTH legs have real OI.

    Far-OTM puts above spot carry ~zero OI while calls there are liquid, so a
    naive ΣPut/ΣCall over a symmetric strike window is structurally < 1 and
    would label almost every script bearish. Restricting to two-sided strikes
    removes that bias.
    """
    if not rows:
        return []
    peak = max((max(r.call.oi, r.put.oi) for r in rows), default=0)
    if peak <= 0:
        return []
    floor = peak * _LIQUID_SHARE
    return [r for r in rows if r.call.oi >= floor and r.put.oi >= floor]


# --------------------------------------------------------------------------- #
# Individual factors
# --------------------------------------------------------------------------- #

def score_oi_analysis(rows, spot: float) -> FactorScore:
    """Wall balance PLUS what kind of positions are being added.

    The audit's point: OI alone cannot tell option BUYING from option WRITING.
    We blend two views:
      (a) wall balance — put wall below spot vs call wall above spot;
      (b) the premium-change × OI-change matrix (classify.py) — writing vs
          long build-up vs unwinding — which is what the SOP document actually
          specifies.
    """
    from . import classify

    puts_below = [r for r in rows if r.strike <= spot and r.put.oi > 0]
    calls_above = [r for r in rows if r.strike >= spot and r.call.oi > 0]
    if not puts_below or not calls_above:
        return FactorScore("OI Analysis", WEIGHTS["OI Analysis"], 0.0, False,
                           "no two-sided OI walls")
    sup = max(puts_below, key=lambda r: r.put.oi)
    res = max(calls_above, key=lambda r: r.call.oi)
    total = sup.put.oi + res.call.oi
    if total <= 0:
        return FactorScore("OI Analysis", WEIGHTS["OI Analysis"], 0.0, False, "no OI")
    wall_score = _clip((sup.put.oi - res.call.oi) / total)

    # (b) writing/build-up classification, OI-weighted across the window
    num = den = 0.0
    labels = []
    for r in rows:
        for q, is_call in ((r.call, True), (r.put, False)):
            # The matrix needs BOTH premium direction and OI change — with no
            # premium move you cannot tell writing from buying (audit's point),
            # so such rows contribute nothing rather than defaulting to "writing".
            if not q.oi or not q.change_oi or not q.premium_change:
                continue
            label = (classify.classify_call(q.premium_change, q.change_oi) if is_call
                     else classify.classify_put(q.premium_change, q.change_oi))
            w = classify.bias_weight(label)
            if w:
                num += w * q.oi
                den += q.oi
                labels.append(label.value)
    note = (f"support {int(sup.strike)} ({sup.put.oi:,}) vs "
            f"resistance {int(res.strike)} ({res.call.oi:,})")
    if den <= 0:
        return FactorScore("OI Analysis", WEIGHTS["OI Analysis"], wall_score, True, note)

    class_score = _clip(num / den)
    # walls describe where price is capped/floored; the matrix describes who is
    # acting now — weight them evenly.
    score = _clip(0.5 * wall_score + 0.5 * class_score)
    top = max(set(labels), key=labels.count) if labels else ""
    return FactorScore("OI Analysis", WEIGHTS["OI Analysis"], score, True,
                       f"{note}; dominant activity: {top}")


def score_change_in_oi(rows, trustworthy: bool) -> FactorScore:
    """ΔPCR over liquid strikes (fresh positioning)."""
    name = "Change in OI"
    if not trustworthy:
        return FactorScore(name, WEIGHTS[name], 0.0, False,
                           "no previous-close/day-open OI baseline")
    liq = _liquid_rows(rows) or rows
    call_d = sum(r.call.change_oi for r in liq)
    put_d = sum(r.put.change_oi for r in liq)

    if call_d > 0 and put_d > 0:
        # Both sides adding — the document's ΔPCR applies directly.
        ratio = put_d / call_d
        # 0.80 / 1.20 are the document's bands; ln-scale 0.22 puts them near ±1.
        return FactorScore(name, WEIGHTS[name], _tanh_ratio(ratio, 0.22) or 0.0, True,
                           f"ΔPCR {ratio:.2f} (ΣPutΔ {put_d:,} / ΣCallΔ {call_d:,})")

    # One side (or both) is net UNWINDING. Previously the whole 15% factor was
    # discarded — JIOFIN lost it entirely. Unwinding is directional information:
    #   calls unwinding  = short covering / cap removed  -> bullish
    #   puts  unwinding  = support leaving               -> bearish
    if call_d == 0 and put_d == 0:
        return FactorScore(name, WEIGHTS[name], 0.0, False, "no ΔOI in the window")

    total = abs(call_d) + abs(put_d)
    # put build-up and call unwinding both read bullish; the reverse reads bearish
    signed = (put_d - call_d) / total if total else 0.0
    # a purely one-sided read is weaker evidence than a clean two-sided ΔPCR
    score = _clip(signed) * 0.7
    desc = []
    desc.append(f"ΣCallΔ {call_d:+,}")
    desc.append(f"ΣPutΔ {put_d:+,}")
    kind = ("call unwinding (cap removed)" if call_d < 0 <= put_d
            else "put unwinding (support leaving)" if put_d < 0 <= call_d
            else "both sides unwinding")
    return FactorScore(name, WEIGHTS[name], score, True,
                       f"{kind}: {', '.join(desc)}")


def score_pcr(rows) -> FactorScore:
    """Total-OI PCR over LIQUID strikes only (removes the far-OTM bias)."""
    liq = _liquid_rows(rows)
    if not liq:
        return FactorScore("PCR", WEIGHTS["PCR"], 0.0, False, "no two-sided strikes")
    call_oi = sum(r.call.oi for r in liq)
    put_oi = sum(r.put.oi for r in liq)
    if call_oi <= 0:
        return FactorScore("PCR", WEIGHTS["PCR"], 0.0, False, "no call OI")
    ratio = put_oi / call_oi
    return FactorScore("PCR", WEIGHTS["PCR"], _tanh_ratio(ratio, 0.35) or 0.0, True,
                       f"liquid-strike PCR {ratio:.2f}")


def score_vwap(spot: float, vwap: Optional[float]) -> FactorScore:
    """`spot` here is the VWAP reference price.

    For indices this is the FUTURE's LTP compared with the FUTURE's VWAP — the
    index itself has no traded volume, and mixing index price with futures VWAP
    would bake in the futures premium as a fake deviation.
    """
    if not vwap or not spot:
        return FactorScore("VWAP", WEIGHTS["VWAP"], 0.0, False, "no VWAP")
    dev = (spot / vwap - 1.0)
    return FactorScore("VWAP", WEIGHTS["VWAP"], _clip(dev / 0.01), True,
                       f"spot {'above' if dev >= 0 else 'below'} VWAP by {abs(dev) * 100:.2f}%")


def score_iv(rows, spot: float, atm: float, expiry: str) -> FactorScore:
    """Put/call IV skew at ATM: richer puts = fear = bearish."""
    name = "IV"
    t = bs.years_to_expiry(expiry)
    row = next((r for r in rows if abs(r.strike - atm) < 1e-6), None)
    if not t or row is None or spot <= 0:
        return FactorScore(name, WEIGHTS[name], 0.0, False, "no expiry/ATM data")
    civ = bs.implied_vol(row.call.ltp, spot, row.strike, t, True) if row.call.ltp else None
    piv = bs.implied_vol(row.put.ltp, spot, row.strike, t, False) if row.put.ltp else None
    if civ is None or piv is None:
        return FactorScore(name, WEIGHTS[name], 0.0, False, "IV not solvable")
    skew = piv - civ                      # >0 => puts richer => bearish
    return FactorScore(name, WEIGHTS[name], _clip(-skew / 0.05), True,
                       f"ATM IV call {civ * 100:.1f}% vs put {piv * 100:.1f}%")


def score_delta_gamma(rows, spot: float, expiry: str) -> FactorScore:
    """Delta-weighted OI exposure: which side are writers defending harder?"""
    name = "Delta/Gamma"
    t = bs.years_to_expiry(expiry)
    if not t or spot <= 0:
        return FactorScore(name, WEIGHTS[name], 0.0, False, "no expiry data")
    call_exp = put_exp = 0.0
    used = 0
    for r in rows:
        civ = bs.implied_vol(r.call.ltp, spot, r.strike, t, True) if r.call.ltp else None
        piv = bs.implied_vol(r.put.ltp, spot, r.strike, t, False) if r.put.ltp else None
        if civ and r.call.oi:
            d = bs.delta(spot, r.strike, t, civ, True)
            if d:
                call_exp += abs(d) * r.call.oi
                used += 1
        if piv and r.put.oi:
            d = bs.delta(spot, r.strike, t, piv, False)
            if d:
                put_exp += abs(d) * r.put.oi
                used += 1
    if used < 2 or (call_exp + put_exp) <= 0:
        return FactorScore(name, WEIGHTS[name], 0.0, False, "greeks not solvable")
    score = _clip((put_exp - call_exp) / (put_exp + call_exp))
    return FactorScore(name, WEIGHTS[name], score, True,
                       f"delta-weighted OI put {put_exp:,.0f} vs call {call_exp:,.0f}")


# --------------------------------------------------------------------------- #
# Composite
# --------------------------------------------------------------------------- #

def build_factors(rows, spot: float, atm: float, expiry: str,
                  spot_vwap: Optional[float], bars: Optional[List[dict]],
                  delta_oi_trustworthy: bool,
                  vwap_price: Optional[float] = None,
                  intraday_bars: Optional[List[dict]] = None) -> List[FactorScore]:
    bars = bars or []
    intraday_bars = intraday_bars or []
    ms = market_structure(bars)                       # daily -> structural
    ti = market_structure(intraday_bars)              # 5-min -> tactical
    mo = momentum(bars)
    vo = volume_confirmation(bars)
    return [
        FactorScore("Structural Bias", WEIGHTS["Structural Bias"],
                    float(ms["score"]), bool(ms["available"]),
                    f"daily: {ms['note']}"),
        FactorScore("Tactical Bias", WEIGHTS["Tactical Bias"],
                    float(ti["score"]), bool(ti["available"]),
                    f"5-min: {ti['note']}"),
        score_oi_analysis(rows, spot),
        score_change_in_oi(rows, delta_oi_trustworthy),
        score_pcr(rows),
        score_vwap(vwap_price if vwap_price else spot, spot_vwap),
        FactorScore("Volume", WEIGHTS["Volume"], float(vo["score"]),
                    bool(vo["available"]), str(vo["note"])),
        score_iv(rows, spot, atm, expiry),
        score_delta_gamma(rows, spot, expiry),
        FactorScore("RSI/Momentum", WEIGHTS["RSI/Momentum"], float(mo["score"]),
                    bool(mo["available"]), str(mo["note"])),
    ]


def composite(factors: List[FactorScore]) -> dict:
    """Weighted mean over available factors + coverage."""
    avail = [f for f in factors if f.available]
    wsum = sum(f.weight for f in avail)
    if wsum <= 0:
        return {"score": 0.0, "coverage": 0.0, "direction": "NEUTRAL", "confidence": 0.0}
    score = sum(f.weight * f.score for f in avail) / wsum
    coverage = wsum / sum(f.weight for f in factors)
    if score > DIRECTION_BAND:
        direction = "BULLISH"
    elif score < -DIRECTION_BAND:
        direction = "BEARISH"
    else:
        direction = "NEUTRAL"
    # Confidence scales with conviction AND how much of the model was available.
    confidence = round(_clip(abs(score) / 0.6, 0.0, 1.0) * (0.55 + 0.45 * coverage), 2)
    return {"score": round(score, 3), "coverage": round(coverage, 2),
            "direction": direction, "confidence": confidence}

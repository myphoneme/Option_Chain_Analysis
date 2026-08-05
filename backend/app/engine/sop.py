"""Option-chain decision engine — Redesign_OCA 5-step framework.

Step 1  Directional bias via ΔPCR (ΣPutΔOI / ΣCallΔOI over the ATM±window):
          < 0.80  -> Bearish (Call writing dominant)  -> Buy PE
          > 1.20  -> Bullish (Put writing dominant)   -> Buy CE
          0.80–1.20 -> Neutral / range -> No Trade
        Falls back to Total-OI PCR when Change-in-OI is unavailable (no baseline).
Step 2  Levels (v1.1): support = put wall STRICTLY BELOW spot, resistance =
        call wall STRICTLY ABOVE spot; crossed walls become pivots; the strike
        window widens when a side has no valid candidate. See levels.py.
Step 3  Strike selection: ATM (primary) + slight-ITM (alt).
Step 4  Entry timing via spot-VWAP and option-VWAP.
Step 5  Risk: spot SL at the opposing wall + hard premium SL; T1/T2 at the walls.
Step 6  Execution gate (v1.1): target monotonicity and reward:risk are enforced;
        an invalid setup is downgraded to WAIT rather than displayed. See
        execution_gate.py.

Direction comes from the weighted multi-factor model in scoring.py, not from a
single rule. `confidence` is a MODEL SCORE, not a calibrated probability.
"""
from __future__ import annotations

from typing import List, Optional

from . import classify, pcr
from .execution_gate import apply as gate_apply
from .levels import find_levels
from .scoring import build_factors, composite
from .models import (
    Bias,
    ChainRow,
    ChainSnapshot,
    FactorScore,
    Invalidation,
    PCRScorecard,
    StrategySuggestion,
    StrikeClassification,
    TradeSetup,
    Verdict,
)

# ΔPCR decision bands (Redesign_OCA Step 1).
_BEAR_BAND = 0.80
_BULL_BAND = 1.20
_SL_BUFFER_PCT = 0.0005   # 0.05% of spot (Step 5 spot SL buffer)
_HARD_PREMIUM_SL_PCT = 15.0
# ΔOI must be at least this share of total OI to be treated as a real signal
# (guards against a few contracts of intraday noise producing a confident verdict).
_MIN_DELTA_SHARE = 0.02
# Price action alone is a partial read (the full SOP needs ΔPCR) — cap it.
_PRICE_ONLY_CONF = 0.45
# |day change| below this is treated as flat.
_FLAT_CHANGE_PCT = 0.15


def analyze(
    snap: ChainSnapshot,
    window: int = 5,
    spot_vwap: Optional[float] = None,
    spot_ltp: Optional[float] = None,
    spot_prev_close: Optional[float] = None,
    delta_is_day_open: bool = True,
    bars: Optional[List[dict]] = None,
) -> Verdict:
    evidence: List[str] = []
    interval = snap.infer_strike_interval()
    atm = snap.atm_strike()
    evidence.append(f"[1] Spot {snap.spot} → base/ATM strike {int(atm)} (interval {int(interval)}).")

    win = _window_rows(snap, atm, interval, window)

    # ---- Step 1: directional bias via ΔPCR (fallback Total-OI PCR) --------
    sum_call_oi = sum(r.call.oi for r in win)
    sum_put_oi = sum(r.put.oi for r in win)
    sum_call_doi = sum(r.call.change_oi for r in win)
    sum_put_doi = sum(r.put.change_oi for r in win)

    delta_pcr: Optional[float] = None
    # ΔOI is only a trustworthy directional signal when the fresh positions are a
    # meaningful share of open interest. Without a market-open baseline the ΔOI is
    # a few contracts of intraday noise — using it would yield confident nonsense.
    total_oi = sum_call_oi + sum_put_oi
    delta_mass = sum_call_doi + sum_put_doi
    delta_significant = (
        sum_call_doi > 0 and sum_put_doi > 0
        and total_oi > 0 and (delta_mass / total_oi) >= _MIN_DELTA_SHARE
    )
    if sum_call_doi > 0 and sum_put_doi > 0:
        delta_pcr = sum_put_doi / sum_call_doi

    # -- 1a. OI-based direction (only from ΔPCR against a day-open baseline) --
    # Total-OI PCR is NOT a substitute: for stocks it is structurally < 0.80
    # (far-OTM puts above spot carry ~no OI), so the document's 0.80/1.20 bands
    # would label almost everything bearish. It is reported as context only.
    total_oi_pcr_ctx = (sum_put_oi / sum_call_oi) if sum_call_oi > 0 else None
    oi_direction: Optional[str] = None
    if delta_significant and delta_is_day_open:
        basis = "change-in-oi"
        oi_direction = ("BEARISH" if delta_pcr < _BEAR_BAND
                        else "BULLISH" if delta_pcr > _BULL_BAND else "NEUTRAL")
        evidence.append(
            f"[1] ΔPCR = ΣPutΔOI {sum_put_doi:,} / ΣCallΔOI {sum_call_doi:,} = {delta_pcr:.2f} "
            f"→ {oi_direction} (bands {_BEAR_BAND}/{_BULL_BAND})."
        )
    else:
        basis = "price-action"
        why = ("no day-open OI baseline captured" if not delta_is_day_open
               else f"ΔOI too small ({delta_mass:,} vs {total_oi:,} OI)")
        evidence.append(
            f"[1] No trustworthy ΔPCR ({why}) — Total-OI PCR "
            f"{total_oi_pcr_ctx:.2f} is context only, not a direction. "
            "Falling back to price action." if total_oi_pcr_ctx
            else f"[1] No trustworthy ΔPCR ({why}) and no OI."
        )

    # -- 1b. Price action (the document's Validation Rule) -------------------
    change_pct = None
    if spot_prev_close and spot_prev_close > 0 and snap.spot:
        change_pct = round((snap.spot / spot_prev_close - 1) * 100, 2)
    price_direction = _price_direction(snap.spot, spot_vwap, change_pct)
    if price_direction:
        bits = []
        if change_pct is not None:
            bits.append(f"day {change_pct:+.2f}%")
        if spot_vwap:
            bits.append(f"spot {'above' if snap.spot >= spot_vwap else 'below'} VWAP {spot_vwap:g}")
        evidence.append(f"[1] Price action: {price_direction} ({', '.join(bits)}).")

    # -- 1c. Weighted multi-factor model -----------------------------------
    factors = build_factors(
        rows=win, spot=snap.spot, atm=atm, expiry=snap.expiry,
        spot_vwap=spot_vwap, bars=bars,
        delta_oi_trustworthy=bool(delta_significant and delta_is_day_open),
    )
    comp = composite(factors)
    direction = comp["direction"]
    confidence = comp["confidence"]
    bias = (Bias.BULLISH if direction == "BULLISH"
            else Bias.BEARISH if direction == "BEARISH" else Bias.NO_TRADE)
    top = sorted((f for f in factors if f.available),
                 key=lambda f: abs(f.contribution), reverse=True)[:3]
    agreement = (f"Weighted score {comp['score']:+.2f} "
                 f"(coverage {comp['coverage'] * 100:.0f}%); "
                 f"led by {', '.join(f.name for f in top)}" if top else "No factors available")
    evidence.append(f"[1] {agreement} → {direction} ({confidence:.0%}).")
    for f in factors:
        state = f"{f.score:+.2f}" if f.available else "n/a"
        evidence.append(f"    · {f.name} ({f.weight * 100:.0f}%): {state} — {f.note}")
    the_pcr = delta_pcr if basis == "change-in-oi" else total_oi_pcr_ctx

    # ---- Step 2: support / resistance walls (v1.1 level engine) -----------
    # Hard rule: support must be BELOW spot and resistance ABOVE it. Crossed
    # max-OI strikes become pivots; the window widens if a side has no candidate.
    lv = find_levels(snap.sorted_rows(), snap.spot, win)
    support, resistance = lv.support, lv.resistance
    evidence.append(
        f"[2] Resistance {int(resistance) if resistance else '—'} (call wall above spot, "
        f"OI {lv.resistance_oi:,}); Support {int(support) if support else '—'} "
        f"(put wall below spot, OI {lv.support_oi:,})."
        + (f" {lv.note}." if lv.note else "")
    )

    # ---- Steps 3 + 5: strike selection + trade setup ---------------------
    setup = _build_trade_setup(direction, atm, interval, support, resistance, snap.spot)
    if setup.option_type:
        evidence.append(
            f"[3] {setup.signal}: ATM {int(setup.selected_strike)} {setup.option_type}, "
            f"slight-ITM {int(setup.alt_strike)} {setup.option_type}."
        )
    else:
        evidence.append("[3] Neutral/range — no directional strike selected.")
    _apply_vwap_entry(setup, snap, atm, direction, spot_vwap)
    if setup.entry_state:
        conf_txt = (
            "" if setup.spot_confirms is None
            else f" Spot {'confirms' if setup.spot_confirms else 'does NOT confirm'} vs Spot-VWAP."
        )
        evidence.append(f"[4] Entry (VWAP): {setup.entry_state}.{conf_txt}")
    else:
        evidence.append("[4] Entry: neutral — no VWAP timing needed.")
    if setup.spot_stop_loss is not None:
        evidence.append(
            f"[5] Spot SL {int(setup.spot_stop_loss)}, hard premium SL {int(setup.hard_premium_sl_pct)}% ; "
            f"T1 {int(setup.target1)} (70%), T2 {int(setup.target2) if setup.target2 else '—'} (30%)."
        )

    # ---- Execution gate: block structurally invalid trades ----------------
    gate_ok, gate_fails, rr = gate_apply(setup, snap.spot)
    if setup.option_type or gate_fails:
        if gate_ok:
            evidence.append(
                f"[6] Execution gate PASSED"
                + (f" (reward:risk {rr:.2f})." if rr else ".")
            )
        else:
            evidence.append("[6] Execution gate BLOCKED the trade: " + "; ".join(gate_fails) + ".")

    # ---- table + per-strike classification labels ------------------------
    classifications: List[StrikeClassification] = []
    chain_table: List[ChainRow] = []
    for r in snap.sorted_rows():
        in_win = r in win
        is_sup = support is not None and abs(r.strike - support) < 1e-6
        is_res = resistance is not None and abs(r.strike - resistance) < 1e-6
        classifications.append(StrikeClassification(
            strike=r.strike,
            call_type=classify.classify_call(r.call.premium_change, r.call.change_oi),
            put_type=classify.classify_put(r.put.premium_change, r.put.change_oi),
            is_support=is_sup, is_resistance=is_res,
        ))
        if in_win:
            chain_table.append(ChainRow(
                strike=r.strike,
                call_oi=r.call.oi, call_chg_oi=r.call.change_oi,
                call_pct_chg=_pct_chg(r.call.change_oi, r.call.oi),
                put_oi=r.put.oi, put_chg_oi=r.put.change_oi,
                put_pct_chg=_pct_chg(r.put.change_oi, r.put.oi),
                is_atm=abs(r.strike - atm) < 1e-6, is_support=is_sup, is_resistance=is_res,
            ))

    # informational premium direction
    ce_prem = _mean([r.call.premium_change for r in win])
    pe_prem = _mean([r.put.premium_change for r in win])
    prem_dir = _premium_direction(ce_prem, pe_prem)

    card = _pcr_at(snap.row_at(atm))
    invalidation = _invalidation(setup, direction)
    strategies = _strategies_from_setup(setup)

    return Verdict(
        underlying=snap.underlying, spot=snap.spot, atm=atm, expiry=snap.expiry,
        bias=bias, confidence=confidence, premium_direction=prem_dir,
        support_strike=support, resistance_strike=resistance,
        pcr=card, classifications=classifications, strategies=strategies,
        invalidation=invalidation, evidence=evidence, timestamp=snap.timestamp,
        direction=direction, delta_pcr=delta_pcr, pcr_basis=basis,
        sum_call_oi=sum_call_oi, sum_put_oi=sum_put_oi,
        sum_call_chg_oi=sum_call_doi, sum_put_chg_oi=sum_put_doi,
        chain_table=chain_table, trade_setup=setup,
        spot_ltp=spot_ltp, spot_vwap=spot_vwap,
        spot_prev_close=spot_prev_close, spot_change_pct=change_pct,
        oi_direction=oi_direction, price_direction=price_direction,
        agreement=agreement,
        factors=factors, composite_score=comp["score"], coverage=comp["coverage"],
        pivots=lv.pivots, support_oi=lv.support_oi, resistance_oi=lv.resistance_oi,
        level_note=lv.note, trade_blocked=setup.blocked,
        validation_failures=setup.validation_failures,
    )


def _apply_vwap_entry(setup: TradeSetup, snap: ChainSnapshot, atm: float,
                      direction: str, spot_vwap: Optional[float]) -> None:
    """Step 4 — VWAP entry timing on the selected option + spot confirmation."""
    if not setup.option_type:
        return
    row = snap.row_at(atm)
    oq = None
    if row is not None:
        oq = row.call if setup.option_type == "CE" else row.put
    if oq and oq.vwap > 0 and oq.ltp > 0:
        setup.option_ltp = oq.ltp
        setup.option_vwap = round(oq.vwap, 2)
        if oq.ltp <= oq.vwap * 1.02:
            setup.entry_state = "ENTER — premium at/near Option-VWAP (good entry zone)"
        else:
            pct = (oq.ltp / oq.vwap - 1) * 100
            setup.entry_state = (f"WAIT — premium {pct:.1f}% above Option-VWAP (extended); "
                                 "wait for a pullback toward VWAP")
    else:
        setup.entry_state = "VWAP unavailable (thin volume / after-hours)"
    # spot vs Spot-VWAP direction confirmation
    if spot_vwap:
        if direction == "BEARISH":
            setup.spot_confirms = snap.spot < spot_vwap
        elif direction == "BULLISH":
            setup.spot_confirms = snap.spot > spot_vwap


# --------------------------------------------------------------------------- #
# Trade setup (Steps 3 & 5)
# --------------------------------------------------------------------------- #

def _build_trade_setup(direction, atm, interval, support, resistance, spot) -> TradeSetup:
    if direction == "BULLISH":
        spot_sl = round(support - _SL_BUFFER_PCT * spot, 2) if support else None
        return TradeSetup(
            signal="LONG / Buy Call (CE)", option_type="CE",
            selected_strike=atm, alt_strike=atm - interval,   # slight ITM call = lower strike
            entry_rule=(f"Confirm Spot holds above Spot-VWAP; buy {int(atm)} CE on a pullback "
                        "toward its Option-VWAP (avoid chasing an extended premium)."),
            spot_stop_loss=spot_sl, hard_premium_sl_pct=_HARD_PREMIUM_SL_PCT,
            target1=resistance, target2=(resistance + 2 * interval) if resistance else None,
            rr_note="Aim R:R ≥ 1:1.5. T1 books 70% at resistance; T2 trails 30% via Option-VWAP / ΔPCR flatten.",
        )
    if direction == "BEARISH":
        spot_sl = round(resistance + _SL_BUFFER_PCT * spot, 2) if resistance else None
        return TradeSetup(
            signal="SHORT / Buy Put (PE)", option_type="PE",
            selected_strike=atm, alt_strike=atm + interval,   # slight ITM put = higher strike
            entry_rule=(f"Confirm Spot stays below Spot-VWAP; buy {int(atm)} PE on a pullback "
                        "toward its Option-VWAP (avoid chasing an extended premium)."),
            spot_stop_loss=spot_sl, hard_premium_sl_pct=_HARD_PREMIUM_SL_PCT,
            target1=support, target2=(support - 2 * interval) if support else None,
            rr_note="Aim R:R ≥ 1:1.5. T1 books 70% at support; T2 trails 30% via Option-VWAP / ΔPCR flatten.",
        )
    return TradeSetup(
        signal="No Trade / range", option_type="",
        selected_strike=None, alt_strike=None,
        entry_rule=("PCR sits in the neutral band (0.80–1.20). Avoid buying options; "
                    "consider defined-risk range strategies (e.g. iron condor) or wait."),
        spot_stop_loss=None, hard_premium_sl_pct=None, target1=None, target2=None,
    )


def _strategies_from_setup(setup: TradeSetup) -> List[StrategySuggestion]:
    if not setup.option_type:
        return [StrategySuggestion(
            trader_type="All", action=setup.signal, risk_note=setup.entry_rule)]
    return [
        StrategySuggestion(trader_type="Directional buyer", action=setup.entry_rule,
                           risk_note=setup.rr_note),
    ]


def _invalidation(setup: TradeSetup, direction: str) -> Optional[Invalidation]:
    if direction == "BULLISH" and setup.spot_stop_loss is not None:
        return Invalidation("below", setup.spot_stop_loss,
                            f"Spot closing below {int(setup.spot_stop_loss)} (support wall) "
                            "invalidates the long — exit.")
    if direction == "BEARISH" and setup.spot_stop_loss is not None:
        return Invalidation("above", setup.spot_stop_loss,
                            f"Spot closing above {int(setup.spot_stop_loss)} (resistance wall) "
                            "invalidates the short — exit.")
    return None


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _price_direction(spot: float, vwap: Optional[float], change_pct: Optional[float]) -> Optional[str]:
    """Direction from price action: spot vs session VWAP + day change."""
    votes = 0
    have = False
    if vwap and spot:
        have = True
        votes += 1 if spot >= vwap else -1
    if change_pct is not None:
        have = True
        if abs(change_pct) >= _FLAT_CHANGE_PCT:
            votes += 1 if change_pct > 0 else -1
    if not have:
        return None
    if votes > 0:
        return "BULLISH"
    if votes < 0:
        return "BEARISH"
    return "NEUTRAL"


def _combine(oi_dir: Optional[str], price_dir: Optional[str],
             delta_pcr: Optional[float]) -> tuple:
    """Cross-check OI positioning against price action (document Step 1 + Final Rule)."""
    directional = {"BULLISH", "BEARISH"}
    # Both available
    if oi_dir in directional and price_dir in directional:
        if oi_dir == price_dir:
            return oi_dir, min(1.0, _confidence(delta_pcr) + 0.15), "OI positioning and price action AGREE"
        return "NEUTRAL", 0.15, "OI positioning CONFLICTS with price action (Final Rule: no trade)"
    # OI only
    if oi_dir in directional:
        if price_dir == "NEUTRAL":
            return oi_dir, min(_confidence(delta_pcr), 0.55), "OI positioning directional, price action flat"
        return oi_dir, _confidence(delta_pcr), "OI positioning only (no price-action data)"
    # Price action only — usable but capped: this is not the full SOP
    if price_dir in directional:
        note = ("OI positioning is NEUTRAL (ΔPCR in the 0.80–1.20 band); direction from price action"
                if oi_dir == "NEUTRAL"
                else "Price action only (no trustworthy ΔPCR — capture the OI baseline)")
        return price_dir, _PRICE_ONLY_CONF, note
    return "NEUTRAL", 0.0, "No directional evidence"


def _window_rows(snap: ChainSnapshot, atm: float, interval: float, n: int):
    lo, hi = atm - n * interval, atm + n * interval
    return [r for r in snap.sorted_rows() if lo - 1e-6 <= r.strike <= hi + 1e-6]


def _confidence(the_pcr: Optional[float]) -> float:
    if the_pcr is None:
        return 0.0
    if the_pcr >= _BULL_BAND:
        return round(min(1.0, 0.40 + (the_pcr - _BULL_BAND) / 0.80), 2)
    if the_pcr <= _BEAR_BAND:
        return round(min(1.0, 0.40 + (_BEAR_BAND - the_pcr) / 0.40), 2)
    # neutral band -> low confidence, higher near an edge
    edge_dist = min(the_pcr - _BEAR_BAND, _BULL_BAND - the_pcr)
    return round(max(0.0, 0.30 - edge_dist), 2)


def _pct_chg(chg: int, oi: int) -> float:
    return round((chg / oi) * 100, 2) if oi else 0.0


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _premium_direction(ce_prem: float, pe_prem: float) -> str:
    if ce_prem > 0 and pe_prem < 0:
        return "bullish (Calls rising, Puts falling)"
    if ce_prem < 0 and pe_prem > 0:
        return "bearish (Calls falling, Puts rising)"
    return "mixed"


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

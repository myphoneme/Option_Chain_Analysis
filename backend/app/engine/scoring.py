"""Weighted multi-factor scoring model.

Replaces the brittle single-rule (ΔPCR-only) direction with a blend of nine
factors. Each factor returns a score in [-1, +1] (positive = bullish) plus a
human note. The composite is the weighted mean over *available* factors, so a
missing input dilutes coverage instead of dragging the result toward zero.

    Market Structure   25%
    OI Analysis        20%
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
    "Market Structure": 0.25,
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
    """Support/resistance walls: which side's wall is bigger and closer?"""
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
    # Bigger put wall (support) => bullish.
    score = _clip((sup.put.oi - res.call.oi) / total)
    return FactorScore(
        "OI Analysis", WEIGHTS["OI Analysis"], score, True,
        f"support {int(sup.strike)} ({sup.put.oi:,}) vs resistance {int(res.strike)} ({res.call.oi:,})",
    )


def score_change_in_oi(rows, trustworthy: bool) -> FactorScore:
    """ΔPCR over liquid strikes (fresh positioning)."""
    name = "Change in OI"
    if not trustworthy:
        return FactorScore(name, WEIGHTS[name], 0.0, False,
                           "no previous-close/day-open OI baseline")
    liq = _liquid_rows(rows) or rows
    call_d = sum(r.call.change_oi for r in liq)
    put_d = sum(r.put.change_oi for r in liq)
    if call_d <= 0 or put_d <= 0:
        return FactorScore(name, WEIGHTS[name], 0.0, False,
                           f"one-sided ΔOI (ΣCallΔ {call_d:,}, ΣPutΔ {put_d:,})")
    ratio = put_d / call_d
    # ΔPCR 0.80 / 1.20 are the document's bands; ln-scale ~0.22 puts them near ±1.
    return FactorScore(name, WEIGHTS[name], _tanh_ratio(ratio, 0.22) or 0.0, True,
                       f"ΔPCR {ratio:.2f} (ΣPutΔ {put_d:,} / ΣCallΔ {call_d:,})")


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
                  delta_oi_trustworthy: bool) -> List[FactorScore]:
    bars = bars or []
    ms = market_structure(bars)
    mo = momentum(bars)
    vo = volume_confirmation(bars)
    return [
        FactorScore("Market Structure", WEIGHTS["Market Structure"],
                    float(ms["score"]), bool(ms["available"]), str(ms["note"])),
        score_oi_analysis(rows, spot),
        score_change_in_oi(rows, delta_oi_trustworthy),
        score_pcr(rows),
        score_vwap(spot, spot_vwap),
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

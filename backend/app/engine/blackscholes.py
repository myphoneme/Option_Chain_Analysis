"""Black-Scholes greeks and implied volatility.

XTS market data carries no IV or greeks, so we derive them from the option
premium, spot, strike and time to expiry. Pure standard library.
"""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Optional

RISK_FREE = 0.065          # ~India 1y T-bill
_MIN_T = 1.0 / (365 * 24)  # 1 hour, avoids div-by-zero at expiry


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def years_to_expiry(expiry_token: str, now: Optional[date] = None) -> Optional[float]:
    """'25AUG2026' -> year fraction until expiry (>= 1 hour)."""
    try:
        exp = datetime.strptime(expiry_token, "%d%b%Y").date()
    except (ValueError, TypeError):
        return None
    days = (exp - (now or date.today())).days
    return max(_MIN_T, days / 365.0)


def _d1_d2(s: float, k: float, t: float, vol: float, r: float = RISK_FREE):
    if s <= 0 or k <= 0 or t <= 0 or vol <= 0:
        return None, None
    d1 = (math.log(s / k) + (r + 0.5 * vol * vol) * t) / (vol * math.sqrt(t))
    return d1, d1 - vol * math.sqrt(t)


def price(s: float, k: float, t: float, vol: float, is_call: bool, r: float = RISK_FREE) -> float:
    d1, d2 = _d1_d2(s, k, t, vol, r)
    if d1 is None:
        return max(0.0, (s - k) if is_call else (k - s))
    disc = math.exp(-r * t)
    if is_call:
        return s * _norm_cdf(d1) - k * disc * _norm_cdf(d2)
    return k * disc * _norm_cdf(-d2) - s * _norm_cdf(-d1)


def implied_vol(premium: float, s: float, k: float, t: float, is_call: bool,
                r: float = RISK_FREE) -> Optional[float]:
    """Solve for IV by bisection (robust; no derivative blow-ups)."""
    if premium <= 0 or s <= 0 or k <= 0 or t <= 0:
        return None
    intrinsic = max(0.0, (s - k) if is_call else (k - s))
    if premium < intrinsic * 0.98:      # below intrinsic -> unsolvable/stale
        return None
    lo, hi = 1e-4, 5.0
    if price(s, k, t, hi, is_call, r) < premium:
        return None                      # beyond 500% vol
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if price(s, k, t, mid, is_call, r) < premium:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-5:
            break
    vol = 0.5 * (lo + hi)
    return vol if 0.005 < vol < 4.99 else None


def delta(s: float, k: float, t: float, vol: float, is_call: bool, r: float = RISK_FREE) -> Optional[float]:
    d1, _ = _d1_d2(s, k, t, vol, r)
    if d1 is None:
        return None
    return _norm_cdf(d1) if is_call else _norm_cdf(d1) - 1.0


def gamma(s: float, k: float, t: float, vol: float, r: float = RISK_FREE) -> Optional[float]:
    d1, _ = _d1_d2(s, k, t, vol, r)
    if d1 is None or vol <= 0 or t <= 0:
        return None
    return _norm_pdf(d1) / (s * vol * math.sqrt(t))

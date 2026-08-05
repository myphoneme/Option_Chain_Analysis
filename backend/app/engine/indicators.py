"""Price-derived indicators: market structure, RSI/momentum, volume.

Computed from daily OHLC bars (XTS /instruments/ohlc). All scoring helpers
return a value in [-1, +1] where positive = bullish.
"""
from __future__ import annotations

from typing import Dict, List, Optional, Sequence


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def sma(values: Sequence[float], n: int) -> Optional[float]:
    if len(values) < n or n <= 0:
        return None
    return sum(values[-n:]) / n


def rsi(closes: Sequence[float], period: int = 14) -> Optional[float]:
    """Wilder's RSI. Needs period+1 closes."""
    if len(closes) < period + 1:
        return None
    gains, losses = 0.0, 0.0
    for a, b in zip(closes[-period - 1:-1], closes[-period:]):
        d = b - a
        gains += max(d, 0.0)
        losses += max(-d, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    if avg_loss == 0:
        return 100.0 if avg_gain > 0 else 50.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))


def market_structure(bars: List[dict]) -> Dict[str, object]:
    """Trend structure from daily bars.

    Blends three views: price vs its moving average, higher-highs/higher-lows,
    and where price sits inside the recent range.
    """
    if len(bars) < 4:
        return {"score": 0.0, "available": False, "note": "not enough history"}
    closes = [b["close"] for b in bars]
    highs = [b["high"] for b in bars]
    lows = [b["low"] for b in bars]
    last = closes[-1]

    parts: List[float] = []
    notes: List[str] = []

    n = min(10, len(closes))
    ma = sma(closes, n)
    if ma:
        # ±3% away from the MA saturates the component.
        s = _clip((last / ma - 1.0) / 0.03)
        parts.append(s)
        notes.append(f"{'above' if last >= ma else 'below'} {n}d MA")

    # Higher highs / higher lows over the last two halves of a short window.
    w = min(6, len(bars) // 2)
    if w >= 2:
        recent_h, prior_h = max(highs[-w:]), max(highs[-2 * w:-w])
        recent_l, prior_l = min(lows[-w:]), min(lows[-2 * w:-w])
        hh, hl = recent_h > prior_h, recent_l > prior_l
        ll, lh = recent_l < prior_l, recent_h < prior_h
        if hh and hl:
            parts.append(1.0); notes.append("higher highs & higher lows")
        elif ll and lh:
            parts.append(-1.0); notes.append("lower highs & lower lows")
        else:
            parts.append(0.0); notes.append("mixed structure")

    # Position within the recent range (breakout vs breakdown).
    rng_h, rng_l = max(highs[-n:]), min(lows[-n:])
    if rng_h > rng_l:
        pos = (last - rng_l) / (rng_h - rng_l)     # 0..1
        parts.append(_clip((pos - 0.5) * 2))
        notes.append(f"{pos * 100:.0f}% of {n}d range")

    score = sum(parts) / len(parts) if parts else 0.0
    return {"score": _clip(score), "available": True, "note": "; ".join(notes)}


def momentum(bars: List[dict]) -> Dict[str, object]:
    """RSI-based momentum score."""
    closes = [b["close"] for b in bars]
    r = rsi(closes)
    if r is None:
        return {"score": 0.0, "available": False, "note": "not enough history"}
    # 50 neutral; ±25 points saturates.
    return {"score": _clip((r - 50.0) / 25.0), "available": True, "note": f"RSI {r:.0f}"}


def volume_confirmation(bars: List[dict]) -> Dict[str, object]:
    """Does today's volume confirm today's move?

    Above-average volume amplifies the day's direction; below-average volume on
    a move is weak confirmation.
    """
    if len(bars) < 4:
        return {"score": 0.0, "available": False, "note": "not enough history"}
    vols = [b["volume"] for b in bars]
    n = min(10, len(vols) - 1)
    avg = sum(vols[-n - 1:-1]) / n if n > 0 else 0
    if avg <= 0:
        return {"score": 0.0, "available": False, "note": "no volume history"}
    ratio = vols[-1] / avg
    day_move = bars[-1]["close"] - bars[-2]["close"]
    if day_move == 0:
        return {"score": 0.0, "available": True, "note": f"vol {ratio:.1f}x avg, flat"}
    strength = _clip((ratio - 1.0) / 1.0, 0.0, 1.0)   # 2x average saturates
    score = strength * (1.0 if day_move > 0 else -1.0)
    return {"score": score, "available": True,
            "note": f"vol {ratio:.1f}x avg on {'up' if day_move > 0 else 'down'} day"}

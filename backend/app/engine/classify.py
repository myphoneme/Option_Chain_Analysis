"""SOP Step 4 - Classify Change in OI.

Implements the classification matrix from Lesson 1 sections 9 & 13:
combine premium change with OI change to infer what kind of positions are
being added or removed. Every option trade has a buyer and a seller, so these
labels are *inferred*, never printed directly in the chain (doc's Professional
Warning).
"""
from __future__ import annotations

from .models import PositionType

# Sensitivity band: treat |change| below this as "flat" to avoid labelling noise.
_EPS_PREMIUM = 0.0   # premium is in rupees; exact 0 means no change
_EPS_OI = 0.0        # OI change in contracts


def classify_call(premium_change: float, oi_change: float) -> PositionType:
    if oi_change > _EPS_OI:
        return (PositionType.CALL_LONG_BUILDUP if premium_change > _EPS_PREMIUM
                else PositionType.CALL_WRITING)
    if oi_change < -_EPS_OI:
        return (PositionType.CALL_SHORT_COVERING if premium_change > _EPS_PREMIUM
                else PositionType.CALL_LONG_UNWINDING)
    return PositionType.NEUTRAL


def classify_put(premium_change: float, oi_change: float) -> PositionType:
    if oi_change > _EPS_OI:
        return (PositionType.PUT_LONG_BUILDUP if premium_change > _EPS_PREMIUM
                else PositionType.PUT_WRITING)
    if oi_change < -_EPS_OI:
        return (PositionType.PUT_SHORT_COVERING if premium_change > _EPS_PREMIUM
                else PositionType.PUT_LONG_UNWINDING)
    return PositionType.NEUTRAL


# Directional contribution of each label, in [-1, 1] (+ = bullish).
# Strong: fresh build-up / writing.  Mild: OI-falling variants.
_BIAS_WEIGHT = {
    PositionType.CALL_LONG_BUILDUP: +1.0,
    PositionType.PUT_WRITING: +1.0,
    PositionType.CALL_SHORT_COVERING: +0.4,
    PositionType.PUT_LONG_UNWINDING: +0.4,
    PositionType.CALL_WRITING: -1.0,
    PositionType.PUT_LONG_BUILDUP: -1.0,
    PositionType.PUT_SHORT_COVERING: -0.4,
    PositionType.CALL_LONG_UNWINDING: -0.4,
    PositionType.NEUTRAL: 0.0,
}


def bias_weight(label: PositionType) -> float:
    return _BIAS_WEIGHT[label]

"""Execution gate (v1.1).

The audit's core recommendation: never display a directional trade whose levels
are internally inconsistent. Direction can be right while the trade construction
is unusable — in the 10-instrument sample, target ordering failed in 7 of 8
directional outputs.

Hard validations (audit list, items 1-6):
  LONG   : stop < entry < target_1 < target_2
  SHORT  : stop > entry > target_1 > target_2
  reward/risk >= MIN_RR
Any failure downgrades the trade to WAIT with the reason shown, instead of
printing an invalid setup.
"""
from __future__ import annotations

from typing import List, Optional, Tuple

MIN_RR = 1.5


def _rr(entry: float, stop: float, target: float) -> Optional[float]:
    risk = abs(entry - stop)
    reward = abs(target - entry)
    if risk <= 0:
        return None
    return reward / risk


def validate(setup, spot: float) -> Tuple[bool, List[str], Optional[float]]:
    """Return (passed, failures, reward_risk).

    `setup` is a TradeSetup. Entry reference is the underlying spot, because the
    stop and targets are all expressed in spot terms.
    """
    if not setup or not setup.option_type:
        return True, [], None            # No-Trade output needs no validation

    fails: List[str] = []
    entry = spot
    stop = setup.spot_stop_loss
    t1, t2 = setup.target1, setup.target2
    long_side = setup.option_type == "CE"

    if stop is None:
        fails.append("no stop level")
    if t1 is None:
        fails.append("no target 1")

    if stop is not None and t1 is not None:
        if long_side:
            if not (stop < entry):
                fails.append(f"stop {stop:g} must be below entry {entry:g} for a long")
            if not (t1 > entry):
                fails.append(f"target 1 {t1:g} must be above entry {entry:g} for a long")
            if t2 is not None and not (t2 > t1):
                fails.append(f"target 2 {t2:g} must be above target 1 {t1:g}")
        else:
            if not (stop > entry):
                fails.append(f"stop {stop:g} must be above entry {entry:g} for a short")
            if not (t1 < entry):
                fails.append(f"target 1 {t1:g} must be below entry {entry:g} for a short")
            if t2 is not None and not (t2 < t1):
                fails.append(f"target 2 {t2:g} must be below target 1 {t1:g}")

    rr = _rr(entry, stop, t1) if (stop is not None and t1 is not None) else None
    if rr is not None and rr < MIN_RR and not fails:
        fails.append(f"reward:risk {rr:.2f} below the {MIN_RR} minimum")

    return (not fails), fails, rr


def apply(setup, spot: float):
    """Validate and, on failure, downgrade the setup to WAIT in place."""
    passed, fails, rr = validate(setup, spot)
    if setup is not None:
        setup.reward_risk = round(rr, 2) if rr is not None else None
        setup.validation_failures = fails
        setup.blocked = not passed
        if not passed:
            setup.signal = f"WAIT — {setup.signal.split('—')[0].strip()} blocked by level check"
            setup.entry_rule = (
                "Directional bias stands, but the trade levels are not usable: "
                + "; ".join(fails)
                + ". Wait for a valid wall on each side of spot before acting."
            )
    return passed, fails, rr

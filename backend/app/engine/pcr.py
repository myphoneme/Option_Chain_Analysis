"""SOP Steps 5 & 6 - PCR scorecards and OI-to-Volume conversion.

Formulas from Lesson 1 section 14.1:
  Total OI PCR        = Put OI / Call OI
  Change-in-OI PCR    = Fresh Put OI added / Fresh Call OI added
  Volume PCR          = Put Volume / Call Volume
  OI-to-Volume conv.  = Change in OI / Volume   (per side)
"""
from __future__ import annotations

from typing import Optional


def _safe_ratio(numer: float, denom: float) -> Optional[float]:
    if denom is None or denom == 0:
        return None
    return numer / denom


def total_oi_pcr(put_oi: float, call_oi: float) -> Optional[float]:
    return _safe_ratio(put_oi, call_oi)


def change_oi_pcr(fresh_put_oi: float, fresh_call_oi: float) -> Optional[float]:
    # Change-in-OI PCR = fresh Put OI ADDED / fresh Call OI ADDED. It is only
    # meaningful when both sides are adding (positive). If either side is
    # unwinding (<= 0) the ratio is undefined -> None.
    if fresh_call_oi <= 0 or fresh_put_oi <= 0:
        return None
    return fresh_put_oi / fresh_call_oi


def volume_pcr(put_volume: float, call_volume: float) -> Optional[float]:
    return _safe_ratio(put_volume, call_volume)


def oi_to_volume(change_oi: float, volume: float) -> Optional[float]:
    """Fraction of traded volume that stuck as fresh open interest.

    Returns a fraction (0.046 == 4.6%). Uses absolute change so that both
    build-up and unwinding register as 'conversion into position change'.
    """
    if volume is None or volume == 0:
        return None
    return abs(change_oi) / volume

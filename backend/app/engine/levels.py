"""Support/resistance level engine (v1.1).

The audit found level sanity failing in 9 of 10 snapshots: the engine picked the
max-OI strike on either side of spot without checking which side it was on, so a
strike below spot could be labelled "resistance" and one above it "support".
Every target inherited the error because T1 = support/resistance.

Hard rules enforced here:
  1. support    = highest-ranked PUT wall  STRICTLY BELOW spot
  2. resistance = highest-ranked CALL wall STRICTLY ABOVE spot
  3. a max-OI strike that price has already crossed becomes a PIVOT, never a wall
  4. if no valid candidate exists in the window, widen the window before giving up
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence


@dataclass
class Levels:
    support: Optional[float] = None
    resistance: Optional[float] = None
    support_oi: int = 0
    resistance_oi: int = 0
    pivots: List[float] = None          # crossed max-OI strikes
    support_candidates: List[float] = None
    resistance_candidates: List[float] = None
    note: str = ""

    def __post_init__(self):
        self.pivots = self.pivots or []
        self.support_candidates = self.support_candidates or []
        self.resistance_candidates = self.resistance_candidates or []


def _rank(row, spot: float, is_put: bool) -> float:
    """Wall strength: OI, boosted by fresh build-up, decayed by distance from spot."""
    q = row.put if is_put else row.call
    if q.oi <= 0:
        return 0.0
    score = float(q.oi)
    # fresh positions defending the level count for more
    if q.change_oi > 0:
        score *= 1.0 + min(1.0, q.change_oi / max(q.oi, 1))
    # a wall 10% away matters less than one right at the money
    dist = abs(row.strike - spot) / spot if spot else 0.0
    score *= max(0.25, 1.0 - dist * 5.0)
    return score


def find_levels(all_rows: Sequence, spot: float, window_rows: Sequence = None) -> Levels:
    """Pick a valid support below spot and resistance above spot.

    `window_rows` is the ATM window; `all_rows` is the full chain used to widen
    the search when the window has no valid candidate on a side.
    """
    if not all_rows or not spot:
        return Levels(note="no chain data")

    window_rows = list(window_rows) if window_rows else list(all_rows)
    lv = Levels()

    def pick(rows, is_put: bool):
        side = [r for r in rows
                if (r.strike < spot if is_put else r.strike > spot)
                and (r.put.oi if is_put else r.call.oi) > 0]
        if not side:
            return None
        return max(side, key=lambda r: _rank(r, spot, is_put))

    widened = []
    sup = pick(window_rows, True)
    if sup is None:                       # rule 4 — widen before giving up
        sup = pick(all_rows, True)
        if sup is not None:
            widened.append("support")
    res = pick(window_rows, False)
    if res is None:
        res = pick(all_rows, False)
        if res is not None:
            widened.append("resistance")

    if sup is not None:
        lv.support, lv.support_oi = sup.strike, sup.put.oi
    if res is not None:
        lv.resistance, lv.resistance_oi = res.strike, res.call.oi

    # rule 3 — max-OI strikes price has already crossed are pivots, not walls
    peak_put = max((r for r in all_rows if r.put.oi > 0), key=lambda r: r.put.oi, default=None)
    peak_call = max((r for r in all_rows if r.call.oi > 0), key=lambda r: r.call.oi, default=None)
    if peak_put is not None and peak_put.strike > spot:
        lv.pivots.append(peak_put.strike)          # biggest put wall now overhead
    if peak_call is not None and peak_call.strike < spot:
        lv.pivots.append(peak_call.strike)         # biggest call wall now below
    lv.pivots = sorted(set(lv.pivots))

    lv.support_candidates = sorted(
        {r.strike for r in all_rows if r.strike < spot and r.put.oi > 0}, reverse=True)[:3]
    lv.resistance_candidates = sorted(
        {r.strike for r in all_rows if r.strike > spot and r.call.oi > 0})[:3]

    notes = []
    if widened:
        notes.append(f"widened window for {', '.join(widened)}")
    if lv.pivots:
        notes.append(f"crossed wall(s) relabelled pivot: {', '.join(str(int(p)) for p in lv.pivots)}")
    if lv.support is None:
        notes.append("no valid support below spot")
    if lv.resistance is None:
        notes.append("no valid resistance above spot")
    lv.note = "; ".join(notes)
    return lv

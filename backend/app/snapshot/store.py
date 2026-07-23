"""Snapshot store + chain builder.

XTS provides *current* OI and LTP only — never Change-in-OI. This module
computes ΔOI by diffing against a per-day baseline captured at first sight of
each instrument, and premium change from (LTP - previous close) which the
touchline already carries. This is the server-side work the blueprint calls out.

In production the baseline and rolling snapshots live in TimescaleDB/Redis; this
in-memory version is correct for a single process and is what the API uses at MVP.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from app.engine.models import ChainSnapshot, OptionQuote, StrikeRow
from app.feed.base import Instrument, NormQuote


def estimate_spot_from_chain(rows) -> Optional[float]:
    """Estimate spot via put-call parity when no reference price is available.

    At the ATM strike, CE and PE premiums are closest. Put-call parity gives
    S ≈ K + (C - P). We pick the strike minimising |C - P| and apply the offset.
    Works from option LTPs alone (no OI/volume needed).
    """
    best = None
    for r in rows:
        c, p = r.call.ltp, r.put.ltp
        if c <= 0 or p <= 0:
            continue
        diff = abs(c - p)
        if best is None or diff < best[0]:
            best = (diff, r.strike + (c - p))
    return round(best[1], 2) if best else None


def chain_has_oi(snap: ChainSnapshot) -> bool:
    return any((r.call.oi or r.put.oi) for r in snap.rows)


@dataclass
class _Baseline:
    oi: int


class SnapshotStore:
    """Derives Change-in-OI.

    Precedence for the baseline:
      1. persisted market-open baseline (BaselineStore) -> true day ΔOI;
      2. in-memory first-sighting -> intraday ΔOI from first request.
    """

    def __init__(self, baseline_store=None):
        # key: (segment, instrument_id) -> baseline
        self._baseline: Dict[Tuple[int, int], _Baseline] = {}
        self._baseline_store = baseline_store  # optional BaselineStore

    def set_baseline(self, segment: int, instrument_id: int, oi: int) -> None:
        self._baseline[(segment, instrument_id)] = _Baseline(oi=oi)

    def reset_day(self) -> None:
        self._baseline.clear()

    def _change_oi(self, segment: int, instrument_id: int, current_oi: int) -> int:
        # 1. persisted day-open baseline (survives restarts, shared across requests)
        if self._baseline_store is not None:
            day_open = self._baseline_store.get(segment, instrument_id)
            if day_open is not None:
                return current_oi - day_open
        # 2. in-memory first-sighting fallback
        key = (segment, instrument_id)
        base = self._baseline.get(key)
        if base is None:
            self._baseline[key] = _Baseline(oi=current_oi)
            return 0
        return current_oi - base.oi

    def build_chain(
        self,
        underlying: str,
        spot: float,
        expiry: str,
        instruments: List[Instrument],
        quotes: Dict[int, Tuple[NormQuote, NormQuote]],
        strike_interval: Optional[float] = None,
        timestamp: Optional[str] = None,
    ) -> ChainSnapshot:
        """Assemble a ChainSnapshot from CE/PE instruments + their quotes.

        `quotes` maps instrument_id -> (touchline, oi) as returned by
        XTSAdapter.fetch_quotes_for.
        """
        by_strike: Dict[float, StrikeRow] = {}
        for ins in instruments:
            if ins.strike is None or ins.option_type not in ("CE", "PE"):
                continue
            pair = quotes.get(ins.instrument_id)
            if not pair:
                continue
            tl, oi = pair
            change_oi = self._change_oi(ins.segment, ins.instrument_id, oi.oi)
            premium_change = round(tl.ltp - tl.prev_close, 2) if tl.prev_close else 0.0
            q = OptionQuote(
                ltp=tl.ltp,
                bid=tl.bid,
                ask=tl.ask,
                volume=tl.volume,
                oi=oi.oi,
                change_oi=change_oi,
                premium_change=premium_change,
            )
            row = by_strike.setdefault(ins.strike, StrikeRow(strike=ins.strike))
            if ins.option_type == "CE":
                row.call = q
            else:
                row.put = q

        rows = [by_strike[s] for s in sorted(by_strike)]
        return ChainSnapshot(
            underlying=underlying,
            spot=spot,
            expiry=expiry,
            rows=rows,
            strike_interval=strike_interval,
            timestamp=timestamp,
        )

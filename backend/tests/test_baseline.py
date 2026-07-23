"""Tests for the day-open OI baseline: persistence, ΔOI derivation, scheduler."""
from __future__ import annotations

from datetime import datetime

from app.engine.models import OptionQuote, StrikeRow
from app.feed.base import Instrument, NormQuote
from app.services.scheduler import seconds_until_next
from app.snapshot import BaselineStore, SnapshotStore


def test_baseline_persist_and_reload(tmp_path):
    p = tmp_path / "bl.json"
    b = BaselineStore(path=str(p))
    b.begin_capture()
    b.add([(2, 111, 5000), (2, 222, 8000)])
    assert b.get(2, 111) == 5000
    # reload from disk -> same values (same trade date)
    b2 = BaselineStore(path=str(p))
    assert b2.is_fresh()
    assert b2.get(2, 222) == 8000
    assert b2.status()["count"] == 2


def test_snapshotstore_uses_day_open_baseline(tmp_path):
    b = BaselineStore(path=str(tmp_path / "bl.json"))
    b.begin_capture()
    b.add([(2, 111, 5000)])  # day-open OI = 5000
    store = SnapshotStore(baseline_store=b)
    ins = [Instrument(2, 111, "X 28JUL2026 CE 100", "X", "28JUL2026", "CE", 100, "OPTIDX")]
    tl = NormQuote(2, 111, ltp=10, prev_close=8)
    oi = NormQuote(2, 111, oi=5600)  # current OI = 5600 -> ΔOI = +600
    snap = store.build_chain("X", 100, "28JUL2026", ins, {111: (tl, oi)})
    assert snap.rows[0].call.change_oi == 600


def test_snapshotstore_first_sighting_fallback_when_no_baseline():
    store = SnapshotStore(baseline_store=None)
    ins = [Instrument(2, 111, "X 28JUL2026 CE 100", "X", "28JUL2026", "CE", 100, "OPTIDX")]
    snap = store.build_chain(
        "X", 100, "28JUL2026", ins,
        {111: (NormQuote(2, 111, ltp=10, prev_close=8), NormQuote(2, 111, oi=5600))},
    )
    assert snap.rows[0].call.change_oi == 0  # first sighting = baseline


def test_scheduler_next_run_is_future_weekday_morning():
    # From a Wednesday 02:00 IST (i.e. Tue 20:30 UTC), next 09:16 IST is same day.
    now_utc = datetime(2026, 7, 15, 2, 0, 0)  # 07:30 IST Wed
    secs = seconds_until_next(9, 16, now_utc=now_utc)
    assert 0 < secs <= 24 * 3600
    # roughly 1h46m to 09:16 IST
    assert 6000 < secs < 6800

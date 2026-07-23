"""Lightweight daily scheduler for the market-open baseline capture.

Runs in a daemon thread; sleeps until the next 09:16 IST weekday, captures the
baseline, then loops. IST has no DST, so a fixed UTC+5:30 offset is exact.
No external dependency.

Enable with BASELINE_AUTOCAPTURE=true (default off so it never fires unexpectedly
in dev/CI). The manual endpoint POST /admin/baseline/capture always works.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timedelta

log = logging.getLogger("baseline.scheduler")

_IST = timedelta(hours=5, minutes=30)


def seconds_until_next(hour: int = 9, minute: int = 16, now_utc: datetime = None) -> float:
    now_ist = (now_utc or datetime.utcnow()) + _IST
    target = now_ist.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now_ist:
        target += timedelta(days=1)
    while target.weekday() >= 5:  # 5=Sat, 6=Sun
        target += timedelta(days=1)
    return (target - now_ist).total_seconds()


def start_scheduler(capture_fn, hour: int = 9, minute: int = 16) -> threading.Thread:
    """Start the daily capture loop in a daemon thread. `capture_fn` takes no args."""

    def _loop():
        while True:
            delay = seconds_until_next(hour, minute)
            log.info("baseline scheduler sleeping %.0f min until next capture", delay / 60)
            time.sleep(delay)
            try:
                capture_fn()
            except Exception as e:  # noqa: BLE001 — never let the loop die
                log.error("scheduled baseline capture failed: %s", e)
            time.sleep(90)  # avoid double-fire within the same minute

    t = threading.Thread(target=_loop, name="baseline-scheduler", daemon=True)
    t.start()
    return t

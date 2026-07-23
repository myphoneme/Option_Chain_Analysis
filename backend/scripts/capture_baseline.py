"""Capture the market-open OI baseline (CLI — for cron at ~09:16 IST).

Usage:
    .venv/bin/python scripts/capture_baseline.py            # default tracked set
    .venv/bin/python scripts/capture_baseline.py NIFTY BANKNIFTY
    .venv/bin/python scripts/capture_baseline.py all

Cron (weekdays 09:16 IST):
    16 9 * * 1-5  cd /path/backend && .venv/bin/python scripts/capture_baseline.py >> baseline.log 2>&1
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.feed import build_adapter
from app.services.baseline_capture import capture_baseline
from app.snapshot import BaselineStore


def main():
    args = [a for a in sys.argv[1:] if a.strip()]
    underlyings = None
    if args:
        underlyings = None if args == ["all"] else [a.upper() for a in args]
        if args == ["all"]:
            os.environ["BASELINE_UNDERLYINGS"] = "all"

    adapter = build_adapter()
    store = BaselineStore()
    summary = capture_baseline(adapter, store, underlyings=underlyings)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

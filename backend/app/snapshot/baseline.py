"""Persistent day-open OI baseline.

XTS gives only *current* Open Interest, never previous-day OI. The SOP's
Change-in-OI is measured against the previous close, so we snapshot OI at
market open (~09:15 IST) and treat that as the day baseline:

    Change-in-OI(instrument) = current_oi - baseline_oi

The baseline is persisted to disk (JSON, keyed by trade date) so it survives
process restarts and is shared by every request that day.
"""
from __future__ import annotations

import json
import os
import threading
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

_DEFAULT_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "oi_baseline.json"


class BaselineStore:
    def __init__(self, path: Optional[str] = None):
        self.path = Path(path or os.getenv("BASELINE_PATH", str(_DEFAULT_PATH)))
        self._lock = threading.Lock()
        self._date: Optional[str] = None
        self._data: Dict[str, int] = {}
        self._load()

    @staticmethod
    def _key(segment: int, instrument_id: int) -> str:
        return f"{segment}:{instrument_id}"

    @staticmethod
    def today_str() -> str:
        return date.today().isoformat()

    def is_fresh(self) -> bool:
        return self._date == self.today_str()

    def _load(self) -> None:
        if not self.path.exists():
            return
        try:
            obj = json.loads(self.path.read_text())
            self._date = obj.get("date")
            self._data = {str(k): int(v) for k, v in obj.get("oi", {}).items()}
        except (ValueError, OSError):
            self._date, self._data = None, {}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps({"date": self._date, "oi": self._data}))
        tmp.replace(self.path)  # atomic

    # -- read (hot path) ---------------------------------------------------
    def get(self, segment: int, instrument_id: int) -> Optional[int]:
        if not self.is_fresh():
            return None
        return self._data.get(self._key(segment, instrument_id))

    # -- capture -----------------------------------------------------------
    def begin_capture(self) -> None:
        with self._lock:
            self._date = self.today_str()
            self._data = {}
            self._save()

    def add(self, items: Iterable[Tuple[int, int, int]]) -> None:
        """items: (segment, instrument_id, oi)."""
        with self._lock:
            for seg, iid, oi in items:
                self._data[self._key(seg, iid)] = int(oi)
            self._save()

    def status(self) -> dict:
        return {
            "date": self._date,
            "fresh": self.is_fresh(),
            "count": len(self._data),
            "path": str(self.path),
        }

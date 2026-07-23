"""Market-open OI baseline capture.

Snapshots current OI for tracked underlyings (nearest expiry, all strikes) and
stores it as the day baseline. Run at ~09:15-09:20 IST so the snapshot ≈
previous-day-close OI, which is what the SOP's Change-in-OI is measured against.

Only works with a direct (OI-capable) adapter.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List, Optional

log = logging.getLogger("baseline")

# Default tracked set: all indices + the most liquid stocks. Override with
# BASELINE_UNDERLYINGS="NIFTY,BANKNIFTY,RELIANCE" or pass "all".
_DEFAULT_STOCKS = [
    "RELIANCE", "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK",
    "INFY", "TCS", "ITC", "LT", "BHARTIARTL", "TATAMOTORS", "TATASTEEL",
    "MARUTI", "BAJFINANCE", "HINDUNILVR", "SUNPHARMA", "ADANIENT", "ADANIPORTS",
    "HDFCLIFE", "M&M", "TITAN", "WIPRO", "ONGC", "COALINDIA",
]


def default_underlyings() -> List[str]:
    from app.fno_universe import INDICES

    env = os.getenv("BASELINE_UNDERLYINGS", "").strip()
    indices = [i["symbol"] for i in INDICES]
    if not env:
        return indices + _DEFAULT_STOCKS
    if env.lower() == "all":
        from app.fno_universe import all_underlyings

        return [u["symbol"] for u in all_underlyings()]
    return [s.strip().upper() for s in env.split(",") if s.strip()]


def _chunks(seq, n):
    for i in range(0, len(seq), n):
        yield seq[i : i + n]


def capture_baseline(
    adapter,
    store,
    underlyings: Optional[List[str]] = None,
    chunk_size: int = 50,
) -> dict:
    """Capture and persist the day-open OI baseline. Returns a summary."""
    if not getattr(adapter, "supports_oi", False):
        raise RuntimeError("baseline capture requires a direct (OI-capable) adapter")
    if not hasattr(adapter, "fetch_oi_for"):
        raise RuntimeError("adapter has no fetch_oi_for")

    from app.fno_universe import find

    syms = underlyings or default_underlyings()
    adapter.login()
    store.begin_capture()

    total = 0
    per: Dict[str, int] = {}
    errors: Dict[str, str] = {}
    for sym in syms:
        try:
            meta = find(sym)
            seg = meta.get("segment", 2)
            exp = adapter.nearest_expiry(sym, seg)
            if not exp:
                errors[sym] = "no expiry"
                continue
            ins = [
                i for i in adapter.list_option_instruments(sym, exp, seg)
                if i.option_type in ("CE", "PE")
            ]
            captured = 0
            for chunk in _chunks(ins, chunk_size):
                oi_map = adapter.fetch_oi_for(chunk)
                items = [(i.segment, i.instrument_id, oi_map[i.instrument_id])
                         for i in chunk if i.instrument_id in oi_map]
                if items:
                    store.add(items)
                    captured += len(items)
            per[sym] = captured
            total += captured
        except Exception as e:  # noqa: BLE001 — one bad symbol must not abort the run
            errors[sym] = str(e)[:120]
            log.warning("baseline capture failed for %s: %s", sym, e)

    summary = {
        "date": store.today_str(),
        "underlyings": len(syms),
        "instruments": total,
        "per_underlying": per,
    }
    if errors:
        summary["errors"] = errors
    log.info("baseline captured: %s instruments across %s underlyings", total, len(per))
    return summary

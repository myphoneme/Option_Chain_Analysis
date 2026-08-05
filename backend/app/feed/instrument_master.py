"""XTS instrument master — the canonical instrument-discovery source.

XTS `/instruments/master` returns every instrument for a segment as
pipe-delimited text (~81k lines for NSEFO). We download it once per day, cache
in memory, and use it to enumerate option strikes/expiries per underlying —
robust, unlike the fuzzy `/search/instruments` endpoint.

Line format (option example):
  NSEFO|73925|2|NIFTY|NIFTY26SEP23350CE|OPTIDX|NIFTY-OPTIDX|...|
    2026-09-29T14:30:00|23350|3|NIFTY 29SEP2026 CE 23350|1|1|NIFTY26SEP23350CE
The friendly display field ("NIFTY 29SEP2026 CE 23350") matches _OPT_RE, so we
scan each line's fields for the first match rather than trusting a fixed index
(spread rows shift columns).
"""
from __future__ import annotations

import re
import time
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from .base import Instrument
from .xts import _OPT_RE

# On-disk day cache so restarts don't re-download the ~16 MB master.
_CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "master_cache"

SEG_NAME = {2: "NSEFO", 12: "BSEFO", 5: "MCXFO", 51: "MCXFO"}
# NSE uses OPTIDX/OPTSTK; BSE uses IO (index options) / IF (index futures).
_OPTION_SERIES = {"OPTIDX", "OPTSTK", "OPTFUT", "OPTCUR", "IO"}
_INDEX_OPTION_SERIES = {"OPTIDX", "IO"}
_FUTURE_SERIES = {"FUTIDX", "FUTSTK", "FUTCUR", "FUTCOM", "IF"}
# Plain monthly future tradingsymbol: SYMBOL + DDMMM(+YYYY) + FUT (one date token).
_FUT_SYM_RE = re.compile(r"^[A-Z0-9&._-]+\d{2}[A-Z]{3}(?:\d{2,4})?FUT$")
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}T")


class InstrumentMaster:
    def __init__(self, request: Callable[..., dict]):
        # request(method, path, *, params=None, payload=None) -> dict
        self._request = request
        # segment -> (loaded_date, options{underlying:[Instrument]}, futures{underlying:[(Instrument, expiry_date)]})
        self._cache: Dict[int, tuple] = {}

    def _fetch_master(self, seg_name: str, attempts: int = 3) -> str:
        """Download the master with retries + on-disk day cache (~16 MB)."""
        cache_file = _CACHE_DIR / f"master_{seg_name}_{date.today().isoformat()}.txt"
        if cache_file.exists():
            try:
                return cache_file.read_text()
            except OSError:
                pass
        last_err = None
        for i in range(attempts):
            try:
                raw = self._request(
                    "POST", "/instruments/master",
                    payload={"exchangeSegmentList": [seg_name]},
                    timeout=90,
                )
                result = raw.get("result", raw.get("response", {}).get("result", "")) or ""
                if result:
                    try:
                        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
                        cache_file.write_text(result)
                        for old in _CACHE_DIR.glob(f"master_{seg_name}_*.txt"):
                            if old != cache_file:
                                old.unlink(missing_ok=True)
                    except OSError:
                        pass
                    return result
            except Exception as e:  # noqa: BLE001 — transient network/socket errors
                last_err = e
                time.sleep(1.5 * (i + 1))
        raise RuntimeError(f"instrument master unavailable for {seg_name}: {last_err}")

    def _ensure(self, segment: int) -> Tuple[Dict[str, List[Instrument]], Dict[str, list]]:
        entry = self._cache.get(segment)
        if entry and entry[0] == date.today():
            return entry[1], entry[2]
        seg_name = SEG_NAME.get(segment, "NSEFO")
        result = self._fetch_master(seg_name)
        options: Dict[str, List[Instrument]] = defaultdict(list)
        futures: Dict[str, list] = defaultdict(list)
        for line in (result or "").split("\n"):
            ins = _parse_option_line(line, segment)
            if ins:
                options[ins.underlying].append(ins)
                continue
            fut = _parse_future_line(line, segment)
            if fut:
                futures[fut[0].underlying].append(fut)  # (Instrument, expiry_date)
        for lst in futures.values():
            lst.sort(key=lambda x: x[1])  # nearest expiry first
        self._cache[segment] = (date.today(), options, futures)
        return options, futures

    def options_for(self, underlying: str, expiry: str, segment: int) -> List[Instrument]:
        options, _ = self._ensure(segment)
        rows = options.get(underlying.upper(), [])
        return [r for r in rows if (not expiry or r.expiry == expiry)]

    def expiries_for(self, underlying: str, segment: int) -> List[str]:
        from .xts import XTSAdapter

        options, _ = self._ensure(segment)
        seen: Dict[str, Optional[date]] = {}
        for r in options.get(underlying.upper(), []):
            if r.expiry:
                seen.setdefault(r.expiry, XTSAdapter.parse_expiry(r.expiry))
        dated = sorted(((t, d) for t, d in seen.items() if d), key=lambda x: x[1])
        return [t for t, _ in dated]

    def underlyings(self, segment: int) -> List[dict]:
        """Every tradable F&O option underlying in this segment (authoritative).

        Derived from the exchange master, so newly added / renamed / delisted
        scripts are picked up automatically — no hand-maintained list.
        """
        options, _ = self._ensure(segment)
        out: List[dict] = []
        for sym, rows in options.items():
            if not rows:
                continue
            r = rows[0]
            out.append({
                "symbol": sym,
                "label": sym,
                "segment": segment,
                # NSE index options are OPTIDX; BSE index options are IO.
                "kind": "index" if r.series in _INDEX_OPTION_SERIES else "stock",
                "lot_size": r.lot_size,
                "strike": None,   # engine infers the interval from live strikes
            })
        out.sort(key=lambda u: (u["kind"] != "index", u["symbol"]))
        return out

    def front_future(self, underlying: str, segment: int) -> Optional[Instrument]:
        """Nearest-expiry (front-month) future for the underlying, or None."""
        _, futures = self._ensure(segment)
        today = date.today()
        rows = futures.get(underlying.upper(), [])
        for ins, exp in rows:
            if exp >= today:
                return ins
        return rows[0][0] if rows else None

    def search(self, query: str, segment: int) -> List[Instrument]:
        options, _ = self._ensure(segment)
        q = query.upper()
        out: List[Instrument] = []
        for underlying, rows in options.items():
            if q in underlying:
                out.extend(rows)
        return out


def _parse_future_line(line: str, segment: int) -> Optional[tuple]:
    """Parse a plain monthly FUTURE line -> (Instrument, expiry_date). Skips spreads."""
    parts = line.split("|")
    if len(parts) < 6:
        return None
    series = parts[5]
    if series not in _FUTURE_SERIES:
        return None
    tradingsymbol = parts[4] if len(parts) > 4 else ""
    if "SPD" in line or not _FUT_SYM_RE.match(tradingsymbol):
        return None  # skip calendar spreads
    try:
        iid = int(parts[1])
    except (ValueError, IndexError):
        return None
    underlying = parts[3]
    exp_date = None
    for p in parts:
        if _ISO_RE.match(p):
            try:
                exp_date = datetime.fromisoformat(p).date()
            except ValueError:
                pass
            break
    if exp_date is None:
        return None
    ins = Instrument(
        segment=segment, instrument_id=iid, name=tradingsymbol,
        underlying=underlying, expiry="", option_type="FUT", strike=None, series=series,
    )
    return (ins, exp_date)


def _parse_option_line(line: str, segment: int) -> Optional[Instrument]:
    parts = line.split("|")
    if len(parts) < 6:
        return None
    series = parts[5]
    if series not in _OPTION_SERIES:
        return None
    try:
        iid = int(parts[1])
    except (ValueError, IndexError):
        return None
    # Field 12 is the lot size (contract multiplier), e.g. BAJFINANCE 750.
    lot = 1
    try:
        lot = max(1, int(float(parts[12])))
    except (ValueError, IndexError):
        pass
    # Find the friendly display field ("NIFTY 29SEP2026 CE 23350").
    for p in parts:
        m = _OPT_RE.match(p)
        if m:
            return Instrument(
                segment=segment,
                instrument_id=iid,
                name=p,
                underlying=m.group("underlying"),
                expiry=m.group("expiry"),
                option_type=m.group("type"),
                strike=float(m.group("strike")),
                series=series,
                lot_size=lot,
            )
    return None

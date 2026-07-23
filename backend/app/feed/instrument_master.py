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

from collections import defaultdict
from datetime import date
from typing import Callable, Dict, List, Optional

from .base import Instrument
from .xts import _OPT_RE

SEG_NAME = {2: "NSEFO", 12: "BSEFO", 5: "MCXFO", 51: "MCXFO"}
_OPTION_SERIES = {"OPTIDX", "OPTSTK", "OPTFUT", "OPTCUR"}


class InstrumentMaster:
    def __init__(self, request: Callable[..., dict]):
        # request(method, path, *, params=None, payload=None) -> dict
        self._request = request
        # segment -> (loaded_date, {underlying: [Instrument]})
        self._cache: Dict[int, tuple] = {}

    def _ensure(self, segment: int) -> Dict[str, List[Instrument]]:
        entry = self._cache.get(segment)
        if entry and entry[0] == date.today():
            return entry[1]
        seg_name = SEG_NAME.get(segment, "NSEFO")
        raw = self._request(
            "POST", "/instruments/master",
            payload={"exchangeSegmentList": [seg_name]},
            timeout=60,  # master is ~16 MB
        )
        result = raw.get("result", raw.get("response", {}).get("result", ""))
        by_underlying: Dict[str, List[Instrument]] = defaultdict(list)
        for line in (result or "").split("\n"):
            ins = _parse_option_line(line, segment)
            if ins:
                by_underlying[ins.underlying].append(ins)
        self._cache[segment] = (date.today(), by_underlying)
        return by_underlying

    def options_for(
        self, underlying: str, expiry: str, segment: int
    ) -> List[Instrument]:
        table = self._ensure(segment)
        rows = table.get(underlying.upper(), [])
        return [r for r in rows if (not expiry or r.expiry == expiry)]

    def expiries_for(self, underlying: str, segment: int) -> List[str]:
        from .xts import XTSAdapter

        table = self._ensure(segment)
        seen: Dict[str, Optional[date]] = {}
        for r in table.get(underlying.upper(), []):
            if r.expiry:
                seen.setdefault(r.expiry, XTSAdapter.parse_expiry(r.expiry))
        dated = sorted(((t, d) for t, d in seen.items() if d), key=lambda x: x[1])
        return [t for t, _ in dated]

    def search(self, query: str, segment: int) -> List[Instrument]:
        table = self._ensure(segment)
        q = query.upper()
        out: List[Instrument] = []
        for underlying, rows in table.items():
            if q in underlying:
                out.extend(rows)
        return out


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
            )
    return None

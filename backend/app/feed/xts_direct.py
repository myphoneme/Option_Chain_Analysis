"""Direct XTS MarketData adapter (via internal token).

Calls XTS MarketData directly at ttblaze.iifl.com using a token obtained from the
gateway's internal token endpoint (see token_provider + internal_xts_token_sop.md).

Why this exists: the gateway proxy `marketdata/quote` returns only {ltp, close}
(no OI). The direct XTS batch quotes endpoint returns the full rich payload —
including OpenInterest (message 1510) — and accepts a LIST of instruments, which
fixes both the OI gap and the serial-fetch problem in one move.

Exposes the same public methods as the proxy XTSAdapter so main.py is
adapter-agnostic.

Endpoints (XTS MarketData):
  POST /instruments/quotes                         batch quotes (1501 touchline, 1510 OI)
  GET  /search/instruments?searchString=           instrument search
  GET  /instruments/instrument/symbol              symbol -> instrument id
  GET  /instruments/instrument/expiryDate          expiry list
"""
from __future__ import annotations

import json
import re
from datetime import date
from typing import Dict, List, Optional, Tuple

import requests

from app.config import settings
from .base import FeedAdapter, Instrument, NormQuote
from .token_provider import InternalTokenProvider, TokenError
from .xts import (  # reuse proven parsers
    MSG_OI,
    MSG_TOUCHLINE,
    SEG_NSECM,
    SEG_NSEFO,
    XTSAdapter,
    XTSError,
    _OPT_RE,
)


class XTSDirectAdapter(FeedAdapter):
    name = "xts-direct"
    supports_oi = True  # direct XTS returns per-strike Open Interest (msg 1510)

    def __init__(
        self,
        token_provider: Optional[InternalTokenProvider] = None,
        md_base: Optional[str] = None,
        timeout: float = 20.0,
        session: Optional[requests.Session] = None,
    ):
        self.tp = token_provider or InternalTokenProvider()
        self.md_base = (md_base or settings.XTS_MD_BASE).rstrip("/")
        self.timeout = timeout
        self._session = session or requests.Session()
        from .instrument_master import InstrumentMaster

        self._master = InstrumentMaster(self._request)

    # -- transport ---------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": self.tp.get_token(), "Content-Type": "application/json"}

    def _request(self, method: str, path: str, *, params=None, payload=None, timeout=None, _retry=True) -> dict:
        url = f"{self.md_base}{path}"
        try:
            r = self._session.request(
                method, url, params=params, json=payload,
                headers=self._headers(), timeout=timeout or self.timeout,
            )
        except requests.RequestException as e:
            raise XTSError(f"XTS request failed ({path}): {e}") from e
        if r.status_code in (401, 403) and _retry:
            # token likely expired/rejected -> force one refresh and retry
            self.tp.get_token(force=True)
            return self._request(method, path, params=params, payload=payload, timeout=timeout, _retry=False)
        try:
            data = r.json()
        except ValueError:
            raise XTSError(f"Non-JSON from XTS {path}: {r.text[:200]}")
        if r.status_code >= 400:
            raise XTSError(f"XTS {path} HTTP {r.status_code}: {data}")
        return data

    # -- FeedAdapter -------------------------------------------------------
    def login(self) -> None:
        self.tp.get_token()  # warm/validate the token

    def _batch_raw(self, instruments: List[Instrument], code: int) -> Dict[int, dict]:
        """Batch quote -> {instrument_id: raw quote dict}."""
        if not instruments:
            return {}
        payload = {
            "instruments": [
                {"exchangeSegment": i.segment, "exchangeInstrumentID": i.instrument_id}
                for i in instruments
            ],
            "xtsMessageCode": code,
            "publishFormat": "JSON",
        }
        data = self._request("POST", "/instruments/quotes", payload=payload)
        result = data.get("result", data.get("response", {}).get("result", {}))
        out: Dict[int, dict] = {}
        for s in result.get("listQuotes", []):
            q = json.loads(s) if isinstance(s, str) else s
            iid = q.get("ExchangeInstrumentID") or q.get("exchangeInstrumentID")
            if iid is not None:
                out[int(iid)] = q
        return out

    def fetch_quotes_for(
        self, instruments: List[Instrument], throttle: float = 0.0
    ) -> Dict[int, Tuple[NormQuote, NormQuote]]:
        """Two batch calls (touchline + OI) for the whole list. Returns real OI."""
        tl = self._batch_raw(instruments, MSG_TOUCHLINE)
        oi = self._batch_raw(instruments, MSG_OI)
        out: Dict[int, Tuple[NormQuote, NormQuote]] = {}
        for i in instruments:
            q_tl = tl.get(i.instrument_id)
            if q_tl is None:
                continue
            out[i.instrument_id] = (
                XTSAdapter._parse_touchline(i.segment, i.instrument_id, q_tl),
                XTSAdapter._parse_oi(i.segment, i.instrument_id, oi.get(i.instrument_id, {})),
            )
        return out

    def fetch_touchline_for(
        self, instruments: List[Instrument], throttle: float = 0.0
    ) -> Dict[int, Tuple[NormQuote, NormQuote]]:
        """Single batch touchline call (used for the fast spot-estimate pass)."""
        tl = self._batch_raw(instruments, MSG_TOUCHLINE)
        out: Dict[int, Tuple[NormQuote, NormQuote]] = {}
        for i in instruments:
            q = tl.get(i.instrument_id)
            if q is None:
                continue
            out[i.instrument_id] = (
                XTSAdapter._parse_touchline(i.segment, i.instrument_id, q),
                NormQuote(segment=i.segment, instrument_id=i.instrument_id),
            )
        return out

    def fetch_oi_for(self, instruments: List[Instrument]) -> Dict[int, int]:
        """OI-only batch (single call) -> {instrument_id: open_interest}.

        Used by the market-open baseline capture (no touchline needed).
        """
        raw = self._batch_raw(instruments, MSG_OI)
        out: Dict[int, int] = {}
        for iid, q in raw.items():
            oi = q.get("OpenInterest", q.get("oi"))
            if oi is not None:
                out[iid] = int(oi)
        return out

    def quote(self, segment: int, instrument_id: int) -> NormQuote:
        ins = Instrument(segment, instrument_id, "", "", "", "", None, "")
        raw = self._batch_raw([ins], MSG_TOUCHLINE)
        q = raw.get(instrument_id)
        if q is None:
            raise XTSError(f"No quote for {segment}:{instrument_id}")
        return XTSAdapter._parse_touchline(segment, instrument_id, q)

    def open_interest(self, segment: int, instrument_id: int) -> NormQuote:
        ins = Instrument(segment, instrument_id, "", "", "", "", None, "")
        raw = self._batch_raw([ins], MSG_OI)
        return XTSAdapter._parse_oi(segment, instrument_id, raw.get(instrument_id, {}))

    # -- instrument discovery (via the XTS instrument master) --------------
    def search_instruments(self, query: str, segment: int = SEG_NSEFO) -> List[Instrument]:
        return self._master.search(query, segment)

    def list_option_instruments(
        self, underlying: str, expiry: str, segment: int = SEG_NSEFO
    ) -> List[Instrument]:
        return [
            i for i in self._master.options_for(underlying, expiry, segment)
            if i.option_type in ("CE", "PE")
        ]

    def list_expiries(self, underlying: str, segment: int = SEG_NSEFO) -> List[str]:
        return self._master.expiries_for(underlying, segment)

    def nearest_expiry(
        self, underlying: str, segment: int = SEG_NSEFO, today: Optional[date] = None
    ) -> Optional[str]:
        today = today or date.today()
        exps = self.list_expiries(underlying, segment)
        for t in exps:
            d = XTSAdapter.parse_expiry(t)
            if d and d >= today:
                return t
        return exps[-1] if exps else None

    def reference_price(
        self, underlying: str, kind: str, expiry: str, segment: int = SEG_NSEFO
    ) -> Optional[float]:
        # Spot is resolved by the two-pass put-call-parity estimate in the
        # analysis endpoint (works from option LTPs). No separate call needed.
        return None


def _to_instrument_direct(r: dict) -> Instrument:
    """Parse a raw XTS search item (capitalised keys) into an Instrument."""
    seg = r.get("ExchangeSegment", r.get("exchangeSegment", 0))
    try:
        seg = int(seg)
    except (TypeError, ValueError):
        seg = 0
    iid = r.get("ExchangeInstrumentID", r.get("exchangeInstrumentID", 0))
    name = (
        r.get("DisplayName") or r.get("Name") or r.get("name")
        or r.get("Description") or ""
    )
    series = r.get("Series", r.get("series", ""))
    m = _OPT_RE.match(name)
    if m:
        underlying = m.group("underlying")
        expiry = m.group("expiry")
        opt = m.group("type")
        strike = float(m.group("strike"))
    else:
        underlying, expiry, opt, strike = (name.split(" ")[0] if name else ""), "", "", None
    return Instrument(
        segment=seg, instrument_id=int(iid) if iid else 0, name=name,
        underlying=underlying, expiry=expiry, option_type=opt, strike=strike, series=series,
    )

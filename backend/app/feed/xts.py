"""XTS feed adapter — talks to the phoneme QuantTrade gateway.

Verified against https://quantapi.phoneme.in (audit 13-Jul-2026):
  POST /api/xts/marketdata/login              -> md session token (server keys)
  POST /api/xts/marketdata/search/instrument  -> instrument search
  POST /api/xts/marketdata/quote              -> 1501 touchline / 1510 OI

Gateway gaps this adapter works around (see blueprint fix list):
  * Single XTS session: we hold ONE md-token and refresh on failure, never
    login per request.
  * No chain / expiry / batch endpoints yet: build_chain() enumerates strikes
    from instrument search and fetches quotes (serial fallback until the
    gateway exposes a batch quote).

Message codes: 1501 = Touchline, 1502 = MarketDepth, 1510 = OpenInterest.
Exchange segments: 1 = NSECM, 2 = NSEFO, 11 = BSECM, 12 = BSEFO, 51 = MCXFO.
"""
from __future__ import annotations

import json
import re
import time
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import requests

from .base import FeedAdapter, Instrument, NormQuote

MSG_TOUCHLINE = 1501
MSG_OI = 1510

SEG_NSECM = 1
SEG_NSEFO = 2
SEG_BSECM = 11
SEG_BSEFO = 12
SEG_MCXFO = 51

# Instrument name pattern: "NIFTY 25AUG2026 PE 23400".
# The symbol may contain digits, & . _ or - (M&M, BAJAJ-AUTO, 360ONE, NAM-INDIA,
# GVT&D, NIFTYNXT50) — a letters-only class silently dropped those scripts.
_OPT_RE = re.compile(
    r"^(?P<underlying>[A-Z0-9&._-]+)\s+(?P<expiry>\d{2}[A-Z]{3}\d{4})\s+"
    r"(?P<type>CE|PE)\s+(?P<strike>\d+(?:\.\d+)?)$"
)


class XTSError(RuntimeError):
    pass


class XTSAdapter(FeedAdapter):
    name = "xts"
    supports_oi = False  # gateway proxy quote currently returns only {ltp, close}

    def __init__(
        self,
        base_url: str = "https://quantapi.phoneme.in",
        access_token: Optional[str] = None,
        timeout: float = 15.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token
        self.timeout = timeout
        self._md_token: Optional[str] = None
        self._session_ready: bool = False
        self._session = requests.Session()

    # -- HTTP helpers ------------------------------------------------------
    def _cookies(self) -> Dict[str, str]:
        return {"access_token": self.access_token} if self.access_token else {}

    def _post(self, path: str, payload: dict) -> dict:
        r = self._session.post(
            f"{self.base_url}/api{path}",
            json=payload,
            cookies=self._cookies(),
            timeout=self.timeout,
        )
        if r.status_code == 401:
            raise XTSError("Not authenticated to gateway (access_token invalid/expired).")
        try:
            data = r.json()
        except ValueError:
            raise XTSError(f"Non-JSON response from {path}: {r.text[:200]}")
        if r.status_code >= 400:
            raise XTSError(f"{path} -> HTTP {r.status_code}: {data}")
        return data

    # -- FeedAdapter -------------------------------------------------------
    def login(self, force: bool = False) -> None:
        """Establish the market-data session.

        Handles both gateway generations:
          * old: returns {"token": "..."} (client passes it back per request)
          * new: holds the XTS session server-side and returns
            {"marketdataToken": true, ...} (no client token needed)
        """
        if self._session_ready and not force:
            return
        data = self._post("/xts/marketdata/login", {})
        token = data.get("token")
        server_side = (
            data.get("marketdataToken")
            or data.get("response", {}).get("marketdataToken")
        )
        if token:
            self._md_token = token
            self._session_ready = True
        elif server_side:
            self._md_token = None  # session lives on the gateway
            self._session_ready = True
        else:
            raise XTSError(f"marketdata/login did not establish a session: {data}")

    def search_instruments(self, query: str, segment: int = SEG_NSEFO) -> List[Instrument]:
        data = self._post(
            "/xts/marketdata/search/instrument",
            {"searchString": query, "exchangeSegment": segment},
        )
        out: List[Instrument] = []
        for r in data.get("results", []):
            out.append(self._to_instrument(r))
        return out

    def quote(self, segment: int, instrument_id: int) -> NormQuote:
        raw = self._quote_raw(segment, instrument_id, MSG_TOUCHLINE)
        return self._parse_touchline(segment, instrument_id, raw)

    def open_interest(self, segment: int, instrument_id: int) -> NormQuote:
        raw = self._quote_raw(segment, instrument_id, MSG_OI)
        return self._parse_oi(segment, instrument_id, raw)

    # -- internals ---------------------------------------------------------
    def _quote_raw(self, segment: int, instrument_id: int, code: int, _retry: bool = True) -> dict:
        """Return a normalised inner quote dict, handling both gateway formats.

        old: response.result.listQuotes[0] is a JSON *string* with rich fields
             (LastTradedPrice, OpenInterest, AskInfo, TotalTradedQuantity, ...)
        new: response.result is already an object ({ltp, close, ...}) — currently
             carries LTP/close only (no OI/volume/depth).
        """
        self.login()
        payload = {
            "exchangeSegment": segment,
            "exchangeInstrumentID": instrument_id,
            "xtsMessageCode": code,
        }
        if self._md_token:  # old gateway wants the token echoed back
            payload["token"] = self._md_token
        try:
            data = self._post("/xts/marketdata/quote", payload)
        except XTSError as e:
            msg = str(e)
            if _retry and ("Invalid Token" in msg or "token is missing" in msg.lower()):
                self.login(force=True)
                return self._quote_raw(segment, instrument_id, code, _retry=False)
            raise
        result = data.get("response", {}).get("result", {})
        # Old format: stringified listQuotes.
        if isinstance(result, dict) and result.get("listQuotes"):
            return json.loads(result["listQuotes"][0])
        # New format: result is the quote object itself.
        if isinstance(result, dict) and result:
            return result
        raise XTSError(f"No quote for {segment}:{instrument_id} code {code}: {data}")

    @staticmethod
    def _parse_touchline(segment: int, instrument_id: int, q: dict) -> NormQuote:
        # Field names differ between gateway formats (rich vs simple).
        ltp = q.get("LastTradedPrice", q.get("ltp", 0.0))
        close = q.get("Close", q.get("close", 0.0))
        bid = (q.get("BidInfo") or {}).get("Price", q.get("bid", 0.0))
        ask = (q.get("AskInfo") or {}).get("Price", q.get("ask", 0.0))
        volume = q.get("TotalTradedQuantity", q.get("volume", 0))
        # AverageTradedPrice = TotalValueTraded / TotalTradedQuantity = session VWAP.
        vwap = q.get("AverageTradedPrice", q.get("vwap", 0.0))
        return NormQuote(
            segment=segment,
            instrument_id=instrument_id,
            ltp=float(ltp or 0.0),
            bid=float(bid or 0.0),
            ask=float(ask or 0.0),
            volume=int(volume or 0),
            prev_close=float(close or 0.0),
            vwap=float(vwap or 0.0),
        )

    @staticmethod
    def _parse_oi(segment: int, instrument_id: int, q: dict) -> NormQuote:
        # OpenInterest is only present in the rich format. The simplified gateway
        # response omits it -> oi stays 0 (caller must detect and surface this).
        return NormQuote(
            segment=segment,
            instrument_id=instrument_id,
            oi=int(q.get("OpenInterest", q.get("oi", 0)) or 0),
            underlying_total_oi=int(q.get("UnderlyingTotalOpenInterest", 0) or 0),
        )

    @staticmethod
    def quote_has_oi(q: dict) -> bool:
        """True if the raw quote dict carries Open Interest (rich format)."""
        return "OpenInterest" in q or "oi" in q

    @staticmethod
    def _to_instrument(r: dict) -> Instrument:
        name = r.get("name", "")
        m = _OPT_RE.match(name)
        if m:
            underlying = m.group("underlying")
            expiry = m.group("expiry")
            opt = m.group("type")
            strike = float(m.group("strike"))
        else:
            underlying, expiry, opt, strike = name.split(" ")[0], "", "", None
        return Instrument(
            segment=r.get("exchangeSegment", 0),
            instrument_id=r.get("exchangeInstrumentID", 0),
            name=name,
            underlying=underlying,
            expiry=expiry,
            option_type=opt,
            strike=strike,
            series=r.get("series", ""),
        )

    # -- chain assembly (works around missing gateway chain endpoint) ------
    def list_option_instruments(
        self, underlying: str, expiry: str, segment: int = SEG_NSEFO
    ) -> List[Instrument]:
        """Find all CE/PE instruments for an underlying + expiry via search."""
        results = self.search_instruments(f"{underlying} {expiry}", segment)
        return [
            i for i in results
            if i.underlying == underlying.upper()
            and i.option_type in ("CE", "PE")
            and (not expiry or i.expiry == expiry)
        ]

    @staticmethod
    def parse_expiry(token: str) -> Optional[date]:
        """Parse an expiry token like '25AUG2026' -> date."""
        try:
            return datetime.strptime(token, "%d%b%Y").date()
        except (ValueError, TypeError):
            return None

    def list_expiries(self, underlying: str, segment: int = SEG_NSEFO) -> List[str]:
        """Distinct option expiries for an underlying, soonest first."""
        results = self.search_instruments(underlying, segment)
        seen: Dict[str, Optional[date]] = {}
        for i in results:
            if i.underlying == underlying.upper() and i.option_type in ("CE", "PE") and i.expiry:
                seen.setdefault(i.expiry, self.parse_expiry(i.expiry))
        dated = [(tok, d) for tok, d in seen.items() if d]
        dated.sort(key=lambda x: x[1])
        return [tok for tok, _ in dated]

    def nearest_expiry(
        self, underlying: str, segment: int = SEG_NSEFO, today: Optional[date] = None
    ) -> Optional[str]:
        today = today or date.today()
        for tok in self.list_expiries(underlying, segment):
            d = self.parse_expiry(tok)
            if d and d >= today:
                return tok
        # else fall back to the last known expiry
        exps = self.list_expiries(underlying, segment)
        return exps[-1] if exps else None

    def reference_price(
        self, underlying: str, kind: str, expiry: str, segment: int = SEG_NSEFO
    ) -> Optional[float]:
        """Best-effort spot proxy: equity LTP for stocks, futures LTP for indices.

        Returns None if it cannot be resolved (caller falls back to a put-call
        parity estimate from the option chain).
        """
        try:
            if kind == "stock":
                eqs = self.search_instruments(underlying, SEG_NSECM)
                match = next(
                    (i for i in eqs if i.name.split(" ")[0] == underlying.upper()
                     and i.series in ("EQ", "")),
                    None,
                )
                if match:
                    return self.quote(match.segment, match.instrument_id).ltp
            # index (or stock fallback): use the futures for this expiry
            futs = [
                i for i in self.search_instruments(underlying, segment)
                if i.underlying == underlying.upper() and i.option_type == ""
                and ("FUT" in i.name.upper())
            ]
            if futs:
                return self.quote(futs[0].segment, futs[0].instrument_id).ltp
        except XTSError:
            return None
        return None

    def fetch_quotes_for(
        self, instruments: List[Instrument], throttle: float = 0.0
    ) -> Dict[int, Tuple[NormQuote, NormQuote]]:
        """Return {instrument_id: (touchline, oi)} for each instrument.

        Serial fallback (gateway lacks batch quote). throttle adds a delay
        between calls if the gateway rate-limits.
        """
        out: Dict[int, Tuple[NormQuote, NormQuote]] = {}
        for ins in instruments:
            try:
                tl = self.quote(ins.segment, ins.instrument_id)
                oi = self.open_interest(ins.segment, ins.instrument_id)
            except XTSError:
                continue  # illiquid / no quote (e.g. after hours) — skip this strike
            out[ins.instrument_id] = (tl, oi)
            if throttle:
                time.sleep(throttle)
        return out

    def fetch_touchline_for(
        self, instruments: List[Instrument], throttle: float = 0.0
    ) -> Dict[int, Tuple[NormQuote, NormQuote]]:
        """Touchline-only fetch (1 call/instrument), fault-tolerant.

        Skips instruments the gateway can't quote (illiquid / after-hours) so a
        few empty strikes don't fail the whole chain. OI stubbed to 0 while the
        gateway does not return it; swap to fetch_quotes_for when OI is restored.
        """
        out: Dict[int, Tuple[NormQuote, NormQuote]] = {}
        for ins in instruments:
            try:
                tl = self.quote(ins.segment, ins.instrument_id)
            except XTSError:
                continue
            out[ins.instrument_id] = (tl, NormQuote(segment=ins.segment, instrument_id=ins.instrument_id))
            if throttle:
                time.sleep(throttle)
        return out

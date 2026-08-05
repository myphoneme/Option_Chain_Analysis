"""Feed-adapter abstraction.

Every data source (XTS today; TrueData / Global Datafeeds at >100 users) is
normalised to the same internal shape at the ingestion boundary, so switching
vendors is a config change, not a rewrite (blueprint section 4).
"""
from __future__ import annotations

import abc
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Instrument:
    segment: int
    instrument_id: int
    name: str            # e.g. "NIFTY 25AUG2026 PE 23400"
    underlying: str      # "NIFTY"
    expiry: str          # "25AUG2026"
    option_type: str     # "CE" / "PE" / "" (for futures/equity)
    strike: Optional[float]
    series: str          # "OPTIDX", "OPTSTK", "EQ", ...
    # Contract multiplier. XTS reports OI/volume in SHARES; NSE displays them in
    # CONTRACTS (lots). Divide by lot_size to match NSE / the SOP document.
    lot_size: int = 1


@dataclass
class NormQuote:
    """Vendor-agnostic quote for one instrument."""

    segment: int
    instrument_id: int
    ltp: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    prev_close: float = 0.0
    vwap: float = 0.0            # session VWAP (XTS AverageTradedPrice)
    oi: int = 0
    underlying_total_oi: int = 0


class FeedAdapter(abc.ABC):
    """Interface the rest of the app depends on. Implemented by XTSAdapter now."""

    name: str = "base"

    @abc.abstractmethod
    def login(self) -> None:
        """Establish / refresh the market-data session (idempotent)."""

    @abc.abstractmethod
    def search_instruments(self, query: str, segment: int) -> List[Instrument]:
        ...

    @abc.abstractmethod
    def quote(self, segment: int, instrument_id: int) -> NormQuote:
        """Touchline (LTP/bid/ask/volume/prev-close) for one instrument."""

    @abc.abstractmethod
    def open_interest(self, segment: int, instrument_id: int) -> NormQuote:
        """Open-interest snapshot for one instrument."""

    # Optional batch path — vendors that support instrument lists override this.
    def quote_batch(self, items: List[tuple]) -> List[NormQuote]:
        """items: list of (segment, instrument_id). Default = serial fallback."""
        return [self.quote(seg, iid) for seg, iid in items]

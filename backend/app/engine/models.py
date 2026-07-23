"""Domain models for the option-chain SOP engine.

Pure standard-library dataclasses + enums so the engine can be unit-tested with
zero third-party dependencies. The API layer (FastAPI/pydantic) adapts these.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class Side(str, Enum):
    CALL = "CALL"
    PUT = "PUT"


class PositionType(str, Enum):
    """The Change-in-OI classification labels from Lesson 1, sections 9 & 13.

    The four primary labels (OI rising) plus the two 'OI falling' variants
    (short covering / long unwinding) that the document uses for e.g. the
    BANKNIFTY 58,200 CE short-covering case.
    """

    CALL_LONG_BUILDUP = "Call Long Build-up"      # CE premium up + CE OI up  -> bullish
    CALL_WRITING = "Call Writing"                 # CE premium down + CE OI up -> bearish / resistance
    CALL_SHORT_COVERING = "Call Short Covering"   # CE premium up + CE OI down -> mild bullish
    CALL_LONG_UNWINDING = "Call Long Unwinding"   # CE premium down + CE OI down -> mild bearish

    PUT_LONG_BUILDUP = "Put Long Build-up"        # PE premium up + PE OI up   -> bearish
    PUT_WRITING = "Put Writing"                   # PE premium down + PE OI up  -> bullish / support
    PUT_SHORT_COVERING = "Put Short Covering"     # PE premium up + PE OI down  -> mild bearish
    PUT_LONG_UNWINDING = "Put Long Unwinding"     # PE premium down + PE OI down -> mild bullish

    NEUTRAL = "Neutral"                           # no fresh change


class Bias(str, Enum):
    BULLISH = "BULLISH"
    BEARISH = "BEARISH"
    NEUTRAL = "NEUTRAL"       # signals cancel -> No Trade
    NO_TRADE = "NO_TRADE"     # conflicting / low-conviction -> No Trade


@dataclass
class OptionQuote:
    """One side (call or put) of a single strike."""

    ltp: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    oi: int = 0
    change_oi: int = 0            # fresh change in OI vs previous snapshot / prev close
    premium_change: float = 0.0   # LTP change vs previous snapshot / prev close
    iv: Optional[float] = None


@dataclass
class StrikeRow:
    strike: float
    call: OptionQuote = field(default_factory=OptionQuote)
    put: OptionQuote = field(default_factory=OptionQuote)


@dataclass
class ChainSnapshot:
    """A full option chain at a moment in time for one underlying + expiry."""

    underlying: str
    spot: float
    expiry: str
    rows: List[StrikeRow]
    timestamp: Optional[str] = None
    strike_interval: Optional[float] = None   # inferred if None

    def sorted_rows(self) -> List[StrikeRow]:
        return sorted(self.rows, key=lambda r: r.strike)

    def infer_strike_interval(self) -> float:
        if self.strike_interval:
            return self.strike_interval
        rows = self.sorted_rows()
        diffs = [round(b.strike - a.strike, 4) for a, b in zip(rows, rows[1:])]
        diffs = [d for d in diffs if d > 0]
        return min(diffs) if diffs else 50.0

    def atm_strike(self) -> float:
        """Nearest strike to spot (SOP step 1)."""
        return min(self.rows, key=lambda r: abs(r.strike - self.spot)).strike

    def row_at(self, strike: float) -> Optional[StrikeRow]:
        for r in self.rows:
            if abs(r.strike - strike) < 1e-6:
                return r
        return None


# ---- Output models ---------------------------------------------------------


@dataclass
class StrikeClassification:
    strike: float
    call_type: PositionType
    put_type: PositionType
    is_support: bool = False
    is_resistance: bool = False
    notes: List[str] = field(default_factory=list)


@dataclass
class PCRScorecard:
    total_oi_pcr: Optional[float]
    change_oi_pcr: Optional[float]
    volume_pcr: Optional[float]
    ce_oi_to_volume: Optional[float]   # fraction (0.046 == 4.6%)
    pe_oi_to_volume: Optional[float]


@dataclass
class StrategySuggestion:
    trader_type: str
    action: str
    risk_note: str


@dataclass
class Invalidation:
    direction: str        # "below" / "above"
    level: float
    condition: str


@dataclass
class Verdict:
    underlying: str
    spot: float
    atm: float
    expiry: str
    bias: Bias
    confidence: float                 # 0..1
    premium_direction: str            # human summary of step 2
    support_strike: Optional[float]
    resistance_strike: Optional[float]
    pcr: PCRScorecard
    classifications: List[StrikeClassification]
    strategies: List[StrategySuggestion]
    invalidation: Optional[Invalidation]
    evidence: List[str]               # the 9-step narrative
    timestamp: Optional[str] = None

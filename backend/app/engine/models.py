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
    vwap: float = 0.0             # session VWAP (XTS AverageTradedPrice)
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
class FactorScore:
    """One input of the weighted scoring model."""
    name: str
    weight: float            # 0..1
    score: float             # -1 (bearish) .. +1 (bullish)
    available: bool
    note: str = ""

    @property
    def contribution(self) -> float:
        return self.weight * self.score if self.available else 0.0


@dataclass
class ChainRow:
    """One strike row of the option-chain table (Redesign_OCA layout)."""
    strike: float
    call_oi: int
    call_chg_oi: int
    call_pct_chg: float       # chg_oi / oi * 100
    put_oi: int
    put_chg_oi: int
    put_pct_chg: float
    is_atm: bool = False
    is_support: bool = False
    is_resistance: bool = False


@dataclass
class TradeSetup:
    """Actionable trade setup per Redesign_OCA Steps 3-5."""
    signal: str                    # "LONG / Buy Call (CE)" | "SHORT / Buy Put (PE)" | "No Trade"
    option_type: str               # "CE" | "PE" | ""
    selected_strike: Optional[float]        # ATM
    alt_strike: Optional[float]             # slight ITM
    entry_rule: str
    spot_stop_loss: Optional[float]
    hard_premium_sl_pct: Optional[float]    # e.g. 15.0
    target1: Optional[float]                # 70% exit (nearest S/R)
    target2: Optional[float]                # 30% runner (next S/R)
    rr_note: str = ""
    # --- Step 4: VWAP entry timing ---
    option_ltp: Optional[float] = None      # selected option premium
    option_vwap: Optional[float] = None     # selected option session VWAP
    entry_state: str = ""                   # "ENTER" / "WAIT — extended" / VWAP unavailable
    spot_confirms: Optional[bool] = None    # spot vs Spot-VWAP agrees with direction?


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
    evidence: List[str]               # the 5-step narrative
    timestamp: Optional[str] = None
    # --- Redesign_OCA additions ---
    direction: str = "NEUTRAL"        # BULLISH | BEARISH | NEUTRAL
    delta_pcr: Optional[float] = None       # ΣPutΔOI / ΣCallΔOI over window
    pcr_basis: str = "none"           # "change-in-oi" | "total-oi"
    sum_call_oi: int = 0
    sum_put_oi: int = 0
    sum_call_chg_oi: int = 0
    sum_put_chg_oi: int = 0
    chain_table: List[ChainRow] = field(default_factory=list)
    trade_setup: Optional[TradeSetup] = None
    spot_ltp: Optional[float] = None        # underlying LTP (equity / front future)
    spot_vwap: Optional[float] = None       # underlying session VWAP
    spot_prev_close: Optional[float] = None
    spot_change_pct: Optional[float] = None # day change % (price action)
    oi_direction: Optional[str] = None      # direction from ΔPCR (None if unavailable)
    price_direction: Optional[str] = None   # direction from price action
    agreement: str = ""                     # human summary of the cross-check
    # --- weighted scoring model ---
    factors: List[FactorScore] = field(default_factory=list)
    composite_score: float = 0.0            # -1..+1
    coverage: float = 0.0                   # share of model weight available

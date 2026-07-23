"""SOP analytics engine (pure standard library, fully unit-testable)."""
from .models import (  # noqa: F401
    Bias,
    ChainSnapshot,
    OptionQuote,
    PositionType,
    StrikeRow,
    Verdict,
)
from .sop import analyze  # noqa: F401

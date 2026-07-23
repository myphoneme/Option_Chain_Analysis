"""Case-study data transcribed verbatim from Module 5, Lesson 1 case studies.

These are the engine's ground truth. Every number below is taken directly from
the document (sections 15 and 16). Do not "fix" them to make code pass — fix the
code.
"""
from __future__ import annotations

from app.engine.models import ChainSnapshot, OptionQuote, StrikeRow


def nifty_case_study() -> ChainSnapshot:
    """Section 15: NIFTY at 24,201.90, ATM 24,200, ~11:01 AM.

    Values provided by the document per strike. Where the document does not give
    a raw number (e.g. some OI/volume totals away from ATM) we only populate what
    is stated; the ATM row carries the full PCR inputs from section 15.4.
    """
    rows = [
        # ---- ATM 24,200: full PCR inputs from section 15.4 ----
        StrikeRow(
            strike=24200,
            call=OptionQuote(
                ltp=0.0, premium_change=+61.90,
                oi=239307, change_oi=101297, volume=2213849,
            ),
            put=OptionQuote(
                ltp=0.0, premium_change=-168.55,
                oi=292740, change_oi=249968, volume=1540989,
            ),
        ),
        StrikeRow(
            strike=24100,
            call=OptionQuote(premium_change=+92.25, change_oi=0, oi=0, volume=1),
            put=OptionQuote(premium_change=-138.20, change_oi=151905, oi=151905, volume=900000),
        ),
        StrikeRow(
            strike=24150,
            call=OptionQuote(premium_change=+76.55, change_oi=0, oi=0, volume=1),
            put=OptionQuote(premium_change=-149.80, change_oi=190592, oi=190592, volume=1000000),
        ),
        StrikeRow(
            strike=24250,
            call=OptionQuote(premium_change=+48.50, change_oi=60386, oi=60386, volume=800000),
            put=OptionQuote(premium_change=-10.0, change_oi=-5000, oi=50000, volume=200000),
        ),
        StrikeRow(
            strike=24500,
            call=OptionQuote(premium_change=+6.85, change_oi=69610, oi=300000, volume=1500000),
            put=OptionQuote(premium_change=-5.0, change_oi=-2000, oi=20000, volume=100000),
        ),
    ]
    return ChainSnapshot(
        underlying="NIFTY",
        spot=24201.90,
        expiry="weekly",
        rows=rows,
        strike_interval=50,
        timestamp="2026-xx-xxT11:01:00+05:30",
    )


def banknifty_case_study() -> ChainSnapshot:
    """Section 16: BANKNIFTY at 58,014.20, ATM 58,000, 12:47 PM 10-Jul-2026."""
    rows = [
        StrikeRow(
            strike=58000,
            call=OptionQuote(premium_change=+252.50, change_oi=1681, oi=48233, volume=78055),
            put=OptionQuote(premium_change=-416.90, change_oi=10357, oi=42428, volume=61741),
        ),
        StrikeRow(
            strike=57800,
            call=OptionQuote(premium_change=+283.90, change_oi=500, oi=20000, volume=30000),
            put=OptionQuote(premium_change=-376.30, change_oi=4324, oi=30000, volume=25000),
        ),
        StrikeRow(
            strike=57900,
            call=OptionQuote(premium_change=+267.90, change_oi=600, oi=22000, volume=35000),
            put=OptionQuote(premium_change=-390.60, change_oi=4203, oi=32000, volume=28000),
        ),
        StrikeRow(
            strike=58100,
            call=OptionQuote(premium_change=+233.25, change_oi=809, oi=25000, volume=40000),
            put=OptionQuote(premium_change=-422.65, change_oi=3000, oi=20000, volume=20000),
        ),
        StrikeRow(
            strike=58200,
            call=OptionQuote(premium_change=+226.80, change_oi=-180, oi=26000, volume=30000),
            put=OptionQuote(premium_change=-5.0, change_oi=-1000, oi=15000, volume=10000),
        ),
        StrikeRow(
            strike=58500,
            call=OptionQuote(premium_change=+178.55, change_oi=859, oi=40000, volume=25000),
            put=OptionQuote(premium_change=-3.0, change_oi=-500, oi=8000, volume=5000),
        ),
    ]
    return ChainSnapshot(
        underlying="BANKNIFTY",
        spot=58014.20,
        expiry="weekly",
        rows=rows,
        strike_interval=100,
        timestamp="2026-07-10T12:47:00+05:30",
    )


def conflicting_case() -> ChainSnapshot:
    """Synthetic 'signals disagree' chain -> engine must return No Trade.

    Calls rising with call writing above, puts also being written but volume
    churny; premium mixed. Represents the document's 'No Trade condition'.
    """
    rows = [
        StrikeRow(
            strike=100,
            call=OptionQuote(premium_change=+1.0, change_oi=5000, oi=50000, volume=50000),
            put=OptionQuote(premium_change=+1.0, change_oi=5000, oi=50000, volume=50000),
        ),
        StrikeRow(
            strike=95,
            call=OptionQuote(premium_change=-1.0, change_oi=5000, oi=40000, volume=40000),
            put=OptionQuote(premium_change=-1.0, change_oi=5000, oi=40000, volume=40000),
        ),
        StrikeRow(
            strike=105,
            call=OptionQuote(premium_change=+1.0, change_oi=5000, oi=40000, volume=40000),
            put=OptionQuote(premium_change=+1.0, change_oi=5000, oi=40000, volume=40000),
        ),
    ]
    return ChainSnapshot(
        underlying="TEST", spot=100, expiry="weekly", rows=rows, strike_interval=5,
    )

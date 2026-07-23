"""Regression tests: the engine must reproduce the document's worked case studies.

Per the blueprint testing strategy, these golden fixtures are ground truth.
Assertions are grounded in explicit numbers/labels stated in Lesson 1.
"""
from __future__ import annotations

import math

import pytest

from app.engine import analyze
from app.engine.classify import classify_call, classify_put
from app.engine.models import Bias, PositionType
from tests.fixtures import banknifty_case_study, conflicting_case, nifty_case_study


def approx(a, b, tol=0.01):
    return abs(a - b) <= tol


# --------------------------------------------------------------------------- #
# NIFTY (section 15)
# --------------------------------------------------------------------------- #

def test_nifty_atm_detection():
    v = analyze(nifty_case_study())
    assert v.atm == 24200  # spot 24,201.90 -> nearest strike 24,200


def test_nifty_pcr_scorecards_match_document():
    v = analyze(nifty_case_study())
    # Section 15.4 exact figures.
    assert approx(v.pcr.total_oi_pcr, 1.22)      # 2,92,740 / 2,39,307
    assert approx(v.pcr.change_oi_pcr, 2.47)     # 2,49,968 / 1,01,297
    assert approx(v.pcr.volume_pcr, 0.70)        # 15,40,989 / 22,13,849


def test_nifty_conversion_match_document():
    v = analyze(nifty_case_study())
    assert approx(v.pcr.ce_oi_to_volume * 100, 4.6, tol=0.1)   # 1,01,297 / 22,13,849
    assert approx(v.pcr.pe_oi_to_volume * 100, 16.2, tol=0.1)  # 2,49,968 / 15,40,989


def test_nifty_classifications():
    # ATM Call: premium +61.90, OI +1,01,297 -> Call long build-up
    assert classify_call(61.90, 101297) == PositionType.CALL_LONG_BUILDUP
    # ATM Put: premium -168.55, OI +2,49,968 -> Put writing
    assert classify_put(-168.55, 249968) == PositionType.PUT_WRITING
    # 24,150 PE: -149.80 / +1,90,592 -> Put writing (fresh support)
    assert classify_put(-149.80, 190592) == PositionType.PUT_WRITING


def test_nifty_verdict_is_bullish_with_support_and_invalidation():
    v = analyze(nifty_case_study())
    # Doc: "fresh positioning at 24,200 is bullish because Put writing is much
    # stronger than Call addition."
    assert v.bias == Bias.BULLISH
    assert v.confidence > 0.35
    # Support sits in the 24,150-24,200 zone; invalidation is a 'break below'.
    assert v.support_strike in (24150, 24200)
    assert v.invalidation is not None
    assert v.invalidation.direction == "below"


# --------------------------------------------------------------------------- #
# BANKNIFTY (section 16)
# --------------------------------------------------------------------------- #

def test_banknifty_atm_detection():
    v = analyze(banknifty_case_study())
    assert v.atm == 58000  # spot 58,014.20 -> nearest strike 58,000


def test_banknifty_pcr_scorecards_match_document():
    v = analyze(banknifty_case_study())
    assert approx(v.pcr.total_oi_pcr, 0.88)      # 42,428 / 48,233
    assert approx(v.pcr.change_oi_pcr, 6.16)     # 10,357 / 1,681
    assert approx(v.pcr.volume_pcr, 0.79)        # 61,741 / 78,055


def test_banknifty_conversion_match_document():
    v = analyze(banknifty_case_study())
    assert approx(v.pcr.ce_oi_to_volume * 100, 2.2, tol=0.1)   # 1,681 / 78,055
    assert approx(v.pcr.pe_oi_to_volume * 100, 16.8, tol=0.1)  # 10,357 / 61,741


def test_banknifty_short_covering_edge_case():
    # 58,200 CE: premium +226.80, OI -180 -> the document's "Call short covering".
    assert classify_call(226.80, -180) == PositionType.CALL_SHORT_COVERING


def test_banknifty_verdict_is_bullish():
    v = analyze(banknifty_case_study())
    # Doc: "market is bullish above 58,000 ... strongest fresh conviction is Put
    # writing at 58,000."
    assert v.bias == Bias.BULLISH
    assert v.support_strike == 58000
    assert v.invalidation.direction == "below"
    assert v.invalidation.level == 58000


# --------------------------------------------------------------------------- #
# No-Trade discipline
# --------------------------------------------------------------------------- #

def test_conflicting_signals_produce_no_trade():
    v = analyze(conflicting_case())
    assert v.bias in (Bias.NO_TRADE, Bias.NEUTRAL)
    assert any("No Trade" in s.action for s in v.strategies)


def test_negative_intraday_delta_oi_does_not_crash():
    # Regression: live intraday OI can DECREASE (unwinding), which made
    # change_oi_pcr negative and crashed math.log2. Engine must stay robust.
    from app.engine.models import ChainSnapshot, OptionQuote, StrikeRow

    rows = [
        StrikeRow(
            strike=100,
            call=OptionQuote(ltp=5, premium_change=1, oi=1000, change_oi=+500, volume=9000),
            put=OptionQuote(ltp=5, premium_change=-1, oi=1000, change_oi=-800, volume=9000),
        ),
        StrikeRow(
            strike=95,
            call=OptionQuote(ltp=8, premium_change=1, oi=800, change_oi=-300, volume=5000),
            put=OptionQuote(ltp=3, premium_change=-1, oi=1200, change_oi=+200, volume=6000),
        ),
        StrikeRow(
            strike=105,
            call=OptionQuote(ltp=3, premium_change=1, oi=900, change_oi=+100, volume=7000),
            put=OptionQuote(ltp=8, premium_change=-1, oi=700, change_oi=-100, volume=4000),
        ),
    ]
    snap = ChainSnapshot("TEST", 100, "weekly", rows, strike_interval=5)
    v = analyze(snap)  # must not raise
    assert v.bias in (Bias.BULLISH, Bias.BEARISH, Bias.NO_TRADE, Bias.NEUTRAL)


def test_change_oi_pcr_matches_manual_arithmetic():
    # Sanity: the two headline ratios the quiz asks about (Q7 = 2.47).
    assert approx(249968 / 101297, 2.47)
    assert approx(10357 / 1681, 6.16)

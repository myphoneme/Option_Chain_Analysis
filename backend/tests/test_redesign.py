"""Golden test for the Redesign_OCA 5-step framework.

Reproduces the document's BANKNIFTY worked example exactly (open 56,883):
ΔPCR 0.734 → Bearish → Buy 56,900 PE, support 56,800, resistance 57,000.
"""
from __future__ import annotations

from app.demo_data import banknifty_redesign_case
from app.engine import analyze
from app.engine.models import Bias


def approx(a, b, tol=0.02):
    return a is not None and abs(a - b) <= tol


def test_redesign_sums_match_document():
    v = analyze(banknifty_redesign_case(), window=6)
    assert v.sum_call_chg_oi == 317331     # ΣCall ΔOI
    assert v.sum_put_chg_oi == 233062      # ΣPut ΔOI


def test_redesign_delta_pcr_and_bearish():
    v = analyze(banknifty_redesign_case(), window=6)
    assert approx(v.delta_pcr, 0.734)      # 233062 / 317331
    assert v.pcr_basis == "change-in-oi"
    assert v.direction == "BEARISH"
    assert v.bias == Bias.BEARISH
    assert v.confidence > 0.4


def test_redesign_support_resistance():
    v = analyze(banknifty_redesign_case(), window=6)
    assert v.support_strike == 56800       # max Put OI (76,284)
    assert v.resistance_strike == 57000    # max Call OI (1,32,907)


def test_redesign_trade_setup():
    v = analyze(banknifty_redesign_case(), window=6)
    ts = v.trade_setup
    assert ts is not None
    assert ts.option_type == "PE"
    assert "Buy Put" in ts.signal
    assert ts.selected_strike == 56900     # ATM
    assert ts.alt_strike == 57000          # slight ITM PE
    assert ts.target1 == 56800             # T1 = support
    # spot SL sits just above the resistance wall (57,000 + 0.05% buffer)
    assert ts.spot_stop_loss > 57000 and ts.spot_stop_loss < 57100


def test_redesign_chain_table_pct_chg():
    v = analyze(banknifty_redesign_case(), window=6)
    row = next(r for r in v.chain_table if r.strike == 56800)
    # %CHNG = chg_oi / oi * 100 (document convention)
    assert approx(row.put_pct_chg, 59040 / 76284 * 100, tol=0.1)
    assert row.is_support is True


def test_neutral_band_is_no_trade():
    # A chain with balanced ΔOI (PCR ~1.0) must be No Trade / range.
    from app.demo_data import conflicting_case
    v = analyze(conflicting_case())
    assert v.bias == Bias.NO_TRADE
    assert v.trade_setup.option_type == ""


def _mk_snapshot_with_vwap(sel_ltp, sel_vwap):
    from app.engine.models import ChainSnapshot, OptionQuote, StrikeRow
    # bearish chain (calls written) so setup picks the ATM PE
    rows = [
        StrikeRow(strike=100,
                  call=OptionQuote(oi=5000, change_oi=8000, ltp=2, vwap=2, volume=9000),
                  put=OptionQuote(oi=3000, change_oi=1000, ltp=sel_ltp, vwap=sel_vwap, volume=9000)),
        StrikeRow(strike=95,
                  call=OptionQuote(oi=4000, change_oi=6000, ltp=6, vwap=6, volume=5000),
                  put=OptionQuote(oi=2000, change_oi=800, ltp=1, vwap=1, volume=4000)),
        StrikeRow(strike=105,
                  call=OptionQuote(oi=4000, change_oi=6000, ltp=1, vwap=1, volume=5000),
                  put=OptionQuote(oi=2000, change_oi=700, ltp=9, vwap=9, volume=4000)),
    ]
    return ChainSnapshot("TEST", 100, "weekly", rows, strike_interval=5)


def test_vwap_entry_enter_when_near_vwap():
    from app.engine import analyze
    # ATM PE premium 49.5 vs its VWAP 49 -> ~1% above (<=2%) -> ENTER
    v = analyze(_mk_snapshot_with_vwap(sel_ltp=49.5, sel_vwap=49), spot_vwap=101)
    ts = v.trade_setup
    assert ts.option_type == "PE"
    assert "ENTER" in ts.entry_state
    assert ts.option_vwap == 49
    assert ts.spot_confirms is True     # spot 100 < spot_vwap 101 (bearish confirmed)


def test_vwap_entry_wait_when_extended():
    from app.engine import analyze
    # ATM PE premium 60 vs VWAP 49 -> ~22% above -> WAIT.
    # spot 100 < spot_vwap 101 so price action agrees with the bearish OI read.
    v = analyze(_mk_snapshot_with_vwap(sel_ltp=60, sel_vwap=49), spot_vwap=101)
    ts = v.trade_setup
    assert "WAIT" in ts.entry_state
    assert ts.spot_confirms is True


def test_conflicting_factors_offset_in_the_weighted_model():
    """Bearish OI vs bullish VWAP must partially cancel, not produce false conviction."""
    from app.engine import analyze
    v = analyze(_mk_snapshot_with_vwap(sel_ltp=50, sel_vwap=49), spot_vwap=99,
                spot_prev_close=97)
    by = {f.name: f for f in v.factors}
    assert by["Change in OI"].score < 0      # OI positioning bearish
    assert by["VWAP"].score > 0              # price action bullish
    # The blend must land inside the extremes rather than at either one.
    assert abs(v.composite_score) < 1.0
    assert v.coverage < 1.0                  # no price history in this fixture


def test_oi_converted_from_shares_to_contracts():
    """XTS reports OI/volume in SHARES; NSE shows CONTRACTS.

    Regression for the BAJFINANCE mismatch: NSE showed 2,253 contracts while we
    displayed 16,89,750 — exactly 750x (the lot size). build_chain must divide.
    """
    from app.feed.base import Instrument, NormQuote
    from app.snapshot import SnapshotStore

    LOT = 750
    ins = [Instrument(2, 111, "BAJFINANCE 25AUG2026 CE 1100", "BAJFINANCE",
                      "25AUG2026", "CE", 1100, "OPTSTK", lot_size=LOT)]
    quotes = {111: (NormQuote(2, 111, ltp=62.0, prev_close=57.8, volume=267 * LOT),
                    NormQuote(2, 111, oi=2253 * LOT))}
    snap = SnapshotStore().build_chain("BAJFINANCE", 1150, "25AUG2026", ins, quotes)
    assert snap.rows[0].call.oi == 2253       # contracts, matches NSE
    assert snap.rows[0].call.volume == 267    # contracts, matches NSE


def test_pcr_is_unaffected_by_unit_conversion():
    # A ratio of two same-unit sums is invariant -> direction never changed.
    from app.engine.pcr import total_oi_pcr
    assert total_oi_pcr(3793, 2253) == total_oi_pcr(3793 * 750, 2253 * 750)


def test_tiny_delta_oi_is_not_trusted():
    """Noise guard: a few contracts of intraday ΔOI must not feed the model.

    Real case (BAJFINANCE, no baseline): ΣCallΔOI 6 / ΣPutΔOI 1 on ~15,000
    contracts of OI once gave ΔPCR 0.17 -> BEARISH 100%.
    """
    from app.engine import analyze
    from app.engine.models import ChainSnapshot, OptionQuote, StrikeRow

    rows = [
        StrikeRow(strike=1150,
                  call=OptionQuote(oi=1600, change_oi=2, ltp=25, vwap=25, volume=500),
                  put=OptionQuote(oi=990, change_oi=1, ltp=25, vwap=25, volume=500)),
        StrikeRow(strike=1100,
                  call=OptionQuote(oi=2252, change_oi=2, ltp=60, vwap=60, volume=300),
                  put=OptionQuote(oi=3793, change_oi=0, ltp=9, vwap=9, volume=300)),
        StrikeRow(strike=1200,
                  call=OptionQuote(oi=3801, change_oi=2, ltp=5, vwap=5, volume=300),
                  put=OptionQuote(oi=449, change_oi=0, ltp=57, vwap=57, volume=300)),
    ]
    snap = ChainSnapshot("BAJFINANCE", 1151, "25AUG2026", rows, strike_interval=50)
    v = analyze(snap)
    by = {f.name: f for f in v.factors}
    assert by["Change in OI"].available is False     # rejected as noise
    assert v.oi_direction is None
    assert v.confidence < 0.60                        # never max conviction


def test_weights_sum_to_one_and_coverage_renormalises():
    """Missing factors must dilute coverage, not drag the score toward zero."""
    from app.engine.scoring import WEIGHTS, composite
    from app.engine.models import FactorScore

    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9

    # Only two factors available, both strongly bullish -> composite must be ~+1
    factors = [FactorScore(n, w, 0.0, False, "") for n, w in WEIGHTS.items()]
    factors[0] = FactorScore("Structural Bias", WEIGHTS["Structural Bias"], 1.0, True, "")
    factors[1] = FactorScore("Tactical Bias", WEIGHTS["Tactical Bias"], 1.0, True, "")
    c = composite(factors)
    expected_cov = WEIGHTS["Structural Bias"] + WEIGHTS["Tactical Bias"]
    assert c["direction"] == "BULLISH"
    assert c["score"] > 0.99                     # renormalised, not 0.25
    assert abs(c["coverage"] - expected_cov) < 1e-6   # coverage reflects the gap
    assert c["confidence"] < 1.0                 # confidence discounted by coverage


def test_market_structure_and_rsi_from_bars():
    from app.engine.indicators import market_structure, momentum, rsi

    up = [{"open": 100 + i, "high": 102 + i, "low": 99 + i,
           "close": 101 + i, "volume": 1000} for i in range(20)]
    down = [{"open": 100 - i, "high": 102 - i, "low": 99 - i,
             "close": 101 - i, "volume": 1000} for i in range(20)]
    assert market_structure(up)["score"] > 0.5
    assert market_structure(down)["score"] < -0.5
    assert momentum(up)["score"] > 0
    assert momentum(down)["score"] < 0
    assert rsi([c["close"] for c in up]) > 60


def test_liquid_strike_pcr_removes_far_otm_bias():
    """Far-OTM puts with ~0 OI must not drag PCR bearish (the KEI/BAJFINANCE bug)."""
    from app.engine.models import OptionQuote, StrikeRow
    from app.engine.scoring import score_pcr

    rows = [
        StrikeRow(strike=100, call=OptionQuote(oi=1000), put=OptionQuote(oi=1000)),
        StrikeRow(strike=105, call=OptionQuote(oi=1000), put=OptionQuote(oi=1000)),
        # far-OTM: calls liquid, puts effectively dead -> must be excluded
        StrikeRow(strike=130, call=OptionQuote(oi=900), put=OptionQuote(oi=0)),
        StrikeRow(strike=140, call=OptionQuote(oi=800), put=OptionQuote(oi=2)),
    ]
    f = score_pcr(rows)
    assert f.available
    assert abs(f.score) < 0.2      # balanced liquid strikes -> ~neutral, not bearish


def test_symbols_with_digits_and_punctuation_parse():
    """Regression: KEI was missing and 6 NSEFO scripts were silently dropped.

    The instrument-name regex only allowed [A-Z]+ for the symbol, so M&M,
    BAJAJ-AUTO, 360ONE, NAM-INDIA, GVT&D and NIFTYNXT50 never parsed.
    """
    from app.feed.xts import XTSAdapter

    cases = [
        ("NIFTYNXT50 28AUG2026 CE 23450", "NIFTYNXT50", "CE", 23450.0),
        ("360ONE 28AUG2026 CE 1000", "360ONE", "CE", 1000.0),
        ("M&M 28AUG2026 PE 3000", "M&M", "PE", 3000.0),
        ("BAJAJ-AUTO 28AUG2026 CE 9000", "BAJAJ-AUTO", "CE", 9000.0),
        ("NAM-INDIA 28AUG2026 CE 800", "NAM-INDIA", "CE", 800.0),
        ("GVT&D 28AUG2026 PE 500", "GVT&D", "PE", 500.0),
        ("KEI 27OCT2026 CE 6600", "KEI", "CE", 6600.0),
    ]
    for name, sym, typ, strike in cases:
        ins = XTSAdapter._to_instrument({
            "exchangeSegment": 2, "exchangeInstrumentID": 1, "name": name, "series": "OPTSTK",
        })
        assert ins.underlying == sym, f"{name} -> {ins.underlying}"
        assert ins.option_type == typ and ins.strike == strike


def test_bse_series_codes_are_recognised():
    """BSE uses IO/IF series (not OPTIDX/FUTIDX) — SENSEX/BANKEX were dropped."""
    from app.feed.instrument_master import _parse_option_line

    line = ("BSEFO|859111|2|SENSEX|SENSEX2690378000CE|IO|SENSEX-IO|12624600859111|"
            "3442.2|0.05|1000|0.05|20|1|-1|SENSEX|2026-09-03T00:00:00|78000|3|"
            "SENSEX 03SEP2026 CE 78000|1|1|SENSEX2690378000CE")
    ins = _parse_option_line(line, 12)
    assert ins is not None
    assert ins.underlying == "SENSEX" and ins.option_type == "CE"
    assert ins.strike == 78000.0 and ins.lot_size == 20

"""v1.1 regressions built from the audit's actual failure cases.

The audit found level sanity failing in 9/10 snapshots and target ordering in
7/8 directional outputs. Each test below reproduces one of those real snapshots
and asserts the v1.1 rules now hold.
"""
from __future__ import annotations

from app.engine import analyze
from app.engine.execution_gate import MIN_RR, validate
from app.engine.levels import find_levels
from app.engine.models import ChainSnapshot, OptionQuote, StrikeRow


def _chain(spot, rows, interval, symbol="TEST"):
    """rows: {strike: (call_oi, put_oi)}"""
    srows = [
        StrikeRow(strike=k,
                  call=OptionQuote(oi=c, ltp=10.0, vwap=10.0, volume=1000),
                  put=OptionQuote(oi=p, ltp=10.0, vwap=10.0, volume=1000))
        for k, (c, p) in sorted(rows.items())
    ]
    return ChainSnapshot(symbol, spot, "25AUG2026", srows, strike_interval=interval)


# --------------------------------------------------------------------------- #
# Rules 1 & 2 — walls must be on the correct side of spot
# --------------------------------------------------------------------------- #

def test_hdfcbank_support_must_be_below_spot():
    """Audit: spot 734.45 but BOTH support and resistance printed 750."""
    snap = _chain(734.45, {
        700: (200, 400), 710: (300, 900), 720: (500, 1500), 730: (900, 2500),
        740: (2000, 800), 750: (9000, 9000), 760: (1500, 200),
    }, 10, "HDFCBANK")
    lv = find_levels(snap.sorted_rows(), snap.spot, snap.sorted_rows())
    assert lv.support is not None and lv.support < 734.45
    assert lv.resistance is not None and lv.resistance > 734.45
    assert lv.support != lv.resistance          # no degenerate pair


def test_reliance_both_walls_above_spot_is_fixed():
    """Audit: spot 1,274.8 with support and resistance both 1,300."""
    snap = _chain(1274.8, {
        1240: (300, 900), 1250: (400, 2000), 1260: (700, 3000), 1270: (1200, 1800),
        1280: (2500, 700), 1290: (3000, 400), 1300: (9000, 9000),
    }, 10, "RELIANCE")
    lv = find_levels(snap.sorted_rows(), snap.spot, snap.sorted_rows())
    assert lv.support < 1274.8 < lv.resistance


def test_hindalco_resistance_below_spot_becomes_pivot():
    """Audit: spot 1,028.15 but resistance printed 1,000 (already crossed)."""
    snap = _chain(1028.15, {
        960: (200, 5000), 980: (400, 2000), 1000: (9000, 800),   # crossed call wall
        1020: (1500, 600), 1040: (2500, 300), 1060: (1200, 100),
    }, 20, "HINDALCO")
    lv = find_levels(snap.sorted_rows(), snap.spot, snap.sorted_rows())
    assert lv.resistance > 1028.15
    assert 1000 in lv.pivots                    # relabelled, not a wall
    assert lv.support < 1028.15


def test_trent_degenerate_equal_levels_is_fixed():
    """Audit: support == resistance == 3,100 removed all practical meaning."""
    snap = _chain(3093.7, {
        3000: (200, 1500), 3050: (400, 2500), 3100: (8000, 8000),
        3150: (3000, 400), 3200: (1500, 200),
    }, 50, "TRENT")
    lv = find_levels(snap.sorted_rows(), snap.spot, snap.sorted_rows())
    assert lv.support != lv.resistance
    assert lv.support < 3093.7 < lv.resistance


# --------------------------------------------------------------------------- #
# Rule 4 — widen the window rather than emit a degenerate pair
# --------------------------------------------------------------------------- #

def test_window_widens_when_no_candidate_in_atm_band():
    """Audit (BANKNIFTY): the most liquid instrument should never fail this."""
    snap = _chain(57769, {
        57000: (500, 9000),                      # only valid support, outside window
        57800: (4000, 300), 57900: (5000, 200),
        58000: (12000, 9000), 58100: (3000, 100),
    }, 100, "BANKNIFTY")
    window = [r for r in snap.sorted_rows() if 57800 <= r.strike <= 58100]
    lv = find_levels(snap.sorted_rows(), snap.spot, window)
    assert lv.support == 57000                   # found by widening
    assert lv.resistance > 57769
    assert "widened" in lv.note


# --------------------------------------------------------------------------- #
# Rules 4-6 — execution gate
# --------------------------------------------------------------------------- #

def test_gate_blocks_short_with_target_above_entry():
    from app.engine.models import TradeSetup
    setup = TradeSetup(signal="SHORT / Buy Put (PE)", option_type="PE",
                       selected_strike=730, alt_strike=740, entry_rule="",
                       spot_stop_loss=750, hard_premium_sl_pct=15,
                       target1=750, target2=730)      # T1 above spot -> invalid
    ok, fails, _ = validate(setup, spot=734.45)
    assert not ok
    assert any("target 1" in f for f in fails)


def test_gate_blocks_long_with_target_below_entry():
    from app.engine.models import TradeSetup
    setup = TradeSetup(signal="LONG / Buy Call (CE)", option_type="CE",
                       selected_strike=1020, alt_strike=1000, entry_rule="",
                       spot_stop_loss=959.49, hard_premium_sl_pct=15,
                       target1=1000, target2=1040)    # T1 below spot -> invalid
    ok, fails, _ = validate(setup, spot=1028.15)
    assert not ok
    assert any("target 1" in f for f in fails)


def test_gate_enforces_minimum_reward_risk():
    from app.engine.models import TradeSetup
    # valid ordering but a very wide stop -> poor R:R (the HINDALCO/SBIN defect)
    setup = TradeSetup(signal="LONG / Buy Call (CE)", option_type="CE",
                       selected_strike=1020, alt_strike=1000, entry_rule="",
                       spot_stop_loss=960, hard_premium_sl_pct=15,
                       target1=1040, target2=1060)
    ok, fails, rr = validate(setup, spot=1028.15)
    assert rr is not None and rr < MIN_RR
    assert not ok and any("reward:risk" in f for f in fails)


def test_gate_passes_a_well_formed_short():
    from app.engine.models import TradeSetup
    setup = TradeSetup(signal="SHORT / Buy Put (PE)", option_type="PE",
                       selected_strike=1270, alt_strike=1280, entry_rule="",
                       spot_stop_loss=1290, hard_premium_sl_pct=15,
                       target1=1240, target2=1220)
    ok, fails, rr = validate(setup, spot=1274.8)
    assert ok and not fails
    assert rr >= MIN_RR


# --------------------------------------------------------------------------- #
# End-to-end: a directional verdict with unusable levels must not be shown
# --------------------------------------------------------------------------- #

def test_endtoend_invalid_levels_downgrade_to_wait():
    """Direction may stand, but the trade must be withheld (audit's core ask)."""
    snap = _chain(1274.8, {
        1270: (1200, 1800), 1280: (2500, 700), 1290: (3000, 400), 1300: (9000, 200),
    }, 10, "RELIANCE")            # no put wall below spot at all
    v = analyze(snap, window=5)
    lv_ok = v.support_strike is None or v.support_strike < v.spot
    assert lv_ok                                   # never a support above spot

    ts = v.trade_setup
    if ts and ts.option_type:
        ok, fails, _ = validate(ts, v.spot)
        # The contract: an invalid setup must be BLOCKED, never displayed as-is.
        if not ok:
            assert ts.blocked, f"invalid setup was not blocked: {fails}"
            assert "WAIT" in ts.signal
            assert v.trade_blocked and v.validation_failures


def test_all_directional_outputs_have_valid_ordering():
    """Sweep several synthetic regimes; no unblocked setup may violate ordering."""
    cases = [
        (1000.0, {950: (200, 4000), 980: (400, 2500), 1000: (900, 1200),
                  1020: (2500, 400), 1050: (5000, 200)}, 20),
        (500.0, {450: (5000, 300), 475: (3000, 500), 500: (1000, 1000),
                 525: (400, 3000), 550: (200, 6000)}, 25),
        (250.0, {240: (800, 900), 245: (700, 950), 250: (1000, 1000),
                 255: (950, 700), 260: (900, 800)}, 5),
    ]
    for spot, rows, interval in cases:
        v = analyze(_chain(spot, rows, interval), window=5)
        ts = v.trade_setup
        if ts and ts.option_type and not ts.blocked:
            ok, fails, _ = validate(ts, v.spot)
            assert ok, f"spot {spot}: unblocked invalid setup {fails}"
        if v.support_strike is not None:
            assert v.support_strike < spot
        if v.resistance_strike is not None:
            assert v.resistance_strike > spot


# --------------------------------------------------------------------------- #
# v1.2 — structural vs tactical, one-sided ΔOI, writing/buying matrix, stops
# --------------------------------------------------------------------------- #

def _bars(n, step, start=100.0, vol=1000):
    return [{"open": start + i * step, "high": start + i * step + 1,
             "low": start + i * step - 1, "close": start + i * step,
             "volume": vol, "oi": 0} for i in range(n)]


def test_structural_and_tactical_are_separate_factors():
    """Audit: a 10-day daily structure can contradict the 5-minute chart."""
    from app.engine.scoring import WEIGHTS, build_factors

    rows = [StrikeRow(strike=100,
                      call=OptionQuote(oi=1000, ltp=5, vwap=5, volume=100),
                      put=OptionQuote(oi=1000, ltp=5, vwap=5, volume=100))]
    factors = build_factors(rows=rows, spot=100, atm=100, expiry="25AUG2026",
                            spot_vwap=None, bars=_bars(20, +1),        # daily UP
                            delta_oi_trustworthy=False,
                            intraday_bars=_bars(20, -1))               # 5-min DOWN
    by = {f.name: f for f in factors}
    assert "Structural Bias" in by and "Tactical Bias" in by
    assert by["Structural Bias"].score > 0      # daily bullish
    assert by["Tactical Bias"].score < 0        # intraday bearish — no longer hidden
    assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9


def test_one_sided_delta_oi_is_used_not_discarded():
    """JIOFIN lost the whole 15% factor when one side was net unwinding."""
    from app.engine.scoring import score_change_in_oi

    # calls unwinding (cap removed) while puts build -> bullish, and AVAILABLE
    rows = [StrikeRow(strike=100,
                      call=OptionQuote(oi=5000, change_oi=-2000),
                      put=OptionQuote(oi=5000, change_oi=+3000))]
    f = score_change_in_oi(rows, trustworthy=True)
    assert f.available is True
    assert f.score > 0
    assert "unwinding" in f.note

    # puts unwinding (support leaving) -> bearish
    rows2 = [StrikeRow(strike=100,
                       call=OptionQuote(oi=5000, change_oi=+3000),
                       put=OptionQuote(oi=5000, change_oi=-2000))]
    f2 = score_change_in_oi(rows2, trustworthy=True)
    assert f2.available is True and f2.score < 0


def test_oi_analysis_uses_writing_vs_buying_matrix():
    """Audit: OI alone cannot distinguish buying from writing."""
    from app.engine.scoring import score_oi_analysis

    # identical OI walls, but premium+OI say PUT WRITING (bullish support build)
    # Puts carry the larger OI and are being WRITTEN (premium down, OI up) —
    # the SOP's bullish support-building signature.
    rows = [
        StrikeRow(strike=95,
                  call=OptionQuote(oi=800, change_oi=200, premium_change=+1.0),
                  put=OptionQuote(oi=3000, change_oi=1500, premium_change=-2.0)),
        StrikeRow(strike=105,
                  call=OptionQuote(oi=800, change_oi=200, premium_change=+1.0),
                  put=OptionQuote(oi=3000, change_oi=1500, premium_change=-2.0)),
    ]
    f = score_oi_analysis(rows, spot=100)
    assert f.available and "dominant activity" in f.note
    assert f.score > 0                      # put writing dominates -> bullish


def test_no_premium_change_means_no_classification():
    """Without premium direction you cannot tell writing from buying."""
    from app.engine.scoring import score_oi_analysis

    rows = [
        StrikeRow(strike=95, call=OptionQuote(oi=1000, change_oi=500),
                  put=OptionQuote(oi=1000, change_oi=500)),
        StrikeRow(strike=105, call=OptionQuote(oi=1000, change_oi=500),
                  put=OptionQuote(oi=1000, change_oi=500)),
    ]
    f = score_oi_analysis(rows, spot=100)
    assert "dominant activity" not in f.note   # falls back to wall balance only


def test_structure_stop_is_capped_so_reward_risk_is_usable():
    """Audit: HINDALCO's ~69-point stop for a ~12-point target was unusable."""
    from app.engine.sop import _structure_stop

    # wall far below spot -> stop must be capped near 1% of spot, not at the wall
    stop = _structure_stop(spot=1028.15, wall=960.0, interval=20, long_side=True)
    assert stop > 1000                       # not dragged down to 960
    assert stop < 1028.15                    # still below entry
    risk = 1028.15 - stop
    cap = max(20, 1028.15 * 0.01)            # max(strike interval, 1% of spot)
    assert risk <= cap + 1                   # bounded, not the 69-point wall stop

    stop_s = _structure_stop(spot=1274.8, wall=1400.0, interval=10, long_side=False)
    assert stop_s < 1300 and stop_s > 1274.8

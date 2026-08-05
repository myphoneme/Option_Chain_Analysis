"""FastAPI surface for the SOP engine.

Endpoints
  GET  /health                       liveness
  GET  /demo/{case}                  run the engine on a built-in case study
                                     (case = nifty | banknifty) — works offline
  POST /analyze                      analyze a client-supplied chain snapshot
  GET  /live/verdict                 build a live chain from XTS and analyze it
                                     (requires XTS gateway access_token)

The live endpoint depends on the phoneme gateway; demo/analyze are pure-engine
and need no network, so the product's core is demonstrable without a feed.
"""
from __future__ import annotations

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.engine import analyze
from app.engine.models import ChainSnapshot, OptionQuote, StrikeRow
from app.serialize import verdict_to_dict
from app.demo_data import banknifty_case_study, banknifty_redesign_case, nifty_case_study

app = FastAPI(title="Option Chain SOP Engine", version="0.1.0")

# Dev CORS: allow the Next.js frontend (localhost:3000). Tighten for production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        os.getenv("FRONTEND_ORIGIN", "http://localhost:3000"),
        "http://127.0.0.1:3000",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Day-open OI baseline (persisted) -> true Change-in-OI. The live store prefers
# it and falls back to intraday first-sighting when no baseline captured yet.
from app.snapshot import BaselineStore as _BaselineStore  # noqa: E402
from app.snapshot import SnapshotStore as _SnapStore  # noqa: E402

_BASELINE = _BaselineStore()
_LIVE_STORE = _SnapStore(baseline_store=_BASELINE)


@app.on_event("startup")
def _maybe_start_scheduler():
    from app.config import settings

    if os.getenv("BASELINE_AUTOCAPTURE", "false").lower() != "true":
        return
    if settings.XTS_MODE != "direct" or not settings.has_app_credentials():
        return
    from app.feed import build_adapter
    from app.services.baseline_capture import capture_baseline
    from app.services.scheduler import start_scheduler

    def _job():
        capture_baseline(build_adapter(), _BASELINE)

    start_scheduler(_job)


@app.get("/admin/baseline/status")
def baseline_status():
    return _BASELINE.status()


@app.post("/admin/baseline/capture")
def baseline_capture(
    underlyings: Optional[str] = Query(None, description="comma list, or 'all'; default tracked set"),
    admin_token: Optional[str] = Query(None),
):
    """Capture the day-open OI baseline now (so ΔOI/classification go live today)."""
    from app.config import settings
    from app.feed import build_adapter
    from app.services.baseline_capture import capture_baseline as _cap

    required = os.getenv("BASELINE_ADMIN_TOKEN")
    if required and admin_token != required:
        raise HTTPException(403, "invalid admin_token")
    if settings.XTS_MODE != "direct" or not settings.has_app_credentials():
        raise HTTPException(400, "baseline capture requires direct XTS mode with app credentials")

    syms = None
    if underlyings and underlyings.lower() != "all":
        syms = [s.strip().upper() for s in underlyings.split(",") if s.strip()]
    elif underlyings and underlyings.lower() == "all":
        os.environ["BASELINE_UNDERLYINGS"] = "all"
    try:
        return _cap(build_adapter(), _BASELINE, underlyings=syms)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"baseline capture failed: {e}")


@app.get("/meta")
def meta():
    """Runtime info the frontend needs (auth mode)."""
    from app.config import settings

    direct = settings.XTS_MODE == "direct" and settings.has_app_credentials()
    return {
        "xts_mode": settings.XTS_MODE,
        # In direct (server-to-server) mode the user does NOT supply a token.
        "needs_user_token": not direct,
    }


@app.get("/scripts")
def scripts():
    """Case-study scripts (offline, fully reproducible)."""
    return {
        "scripts": [
            {"id": "nifty", "label": "NIFTY (case study)", "mode": "demo", "segment": 2},
            {"id": "banknifty", "label": "BANKNIFTY (case study)", "mode": "demo", "segment": 2},
            {"id": "banknifty_redesign", "label": "BANKNIFTY (redesign example)", "mode": "demo", "segment": 2},
        ],
    }


@app.get("/fno/underlyings")
def fno_underlyings():
    """Full F&O underlying universe for the live script selector.

    Sourced from the exchange instrument master (authoritative, auto-updating);
    falls back to the bundled static list if the master is unavailable.
    """
    from app.config import settings
    from app.fno_universe import live_universe, universe

    u = {**universe(), "source": "static"}
    if settings.XTS_MODE == "direct" and settings.has_app_credentials():
        try:
            from app.feed import build_adapter

            u = live_universe(build_adapter())
        except Exception:  # noqa: BLE001 — never break the selector
            pass
    return {
        "indices": u["indices"],
        "stocks": u["stocks"],
        "count": len(u["indices"]) + len(u["stocks"]),
        "source": u.get("source", "static"),
    }


# ---- request models --------------------------------------------------------

class QuoteIn(BaseModel):
    ltp: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    volume: int = 0
    oi: int = 0
    change_oi: int = 0
    premium_change: float = 0.0
    iv: Optional[float] = None


class StrikeIn(BaseModel):
    strike: float
    call: QuoteIn = Field(default_factory=QuoteIn)
    put: QuoteIn = Field(default_factory=QuoteIn)


class ChainIn(BaseModel):
    underlying: str
    spot: float
    expiry: str = "weekly"
    strike_interval: Optional[float] = None
    rows: List[StrikeIn]
    window: int = 3


def _to_snapshot(c: ChainIn) -> ChainSnapshot:
    rows = [
        StrikeRow(
            strike=r.strike,
            call=OptionQuote(**r.call.dict()),
            put=OptionQuote(**r.put.dict()),
        )
        for r in c.rows
    ]
    return ChainSnapshot(
        underlying=c.underlying,
        spot=c.spot,
        expiry=c.expiry,
        rows=rows,
        strike_interval=c.strike_interval,
    )


# ---- endpoints -------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok", "service": "sop-engine", "version": "0.1.0"}


@app.get("/demo/{case}")
def demo(case: str):
    cases = {"nifty": nifty_case_study, "banknifty": banknifty_case_study, "banknifty_redesign": banknifty_redesign_case}
    if case not in cases:
        raise HTTPException(404, f"unknown case '{case}'; try {list(cases)}")
    win = 6 if case == "banknifty_redesign" else 5
    return verdict_to_dict(analyze(cases[case](), window=win))


@app.post("/analyze")
def analyze_chain(chain: ChainIn):
    return verdict_to_dict(analyze(_to_snapshot(chain), window=chain.window))


@app.get("/live/verdict")
def live_verdict(
    underlying: str = Query(..., examples=["RELIANCE"]),
    expiry: Optional[str] = Query(None, description="e.g. 25AUG2026; auto if omitted"),
    spot: Optional[float] = Query(None, description="spot; auto-resolved if omitted"),
    segment: Optional[int] = Query(None, description="2=NSEFO, 12=BSEFO; from universe if omitted"),
    max_strikes: int = Query(11, description="strikes centred on ATM"),
    access_token: Optional[str] = Query(None, description="XTS gateway token"),
):
    """Live path for ANY F&O underlying.

    Resolves segment/expiry/spot automatically, enumerates the chain from XTS,
    computes ΔOI, and runs the SOP engine. Reports `data_quality` so the UI can
    show when OI/volume are missing from the gateway (current known limitation).
    """
    from app.config import settings
    from app.feed import TokenError, XTSError, build_adapter
    from app.fno_universe import find_live
    from app.snapshot import SnapshotStore, chain_has_oi, estimate_spot_from_chain

    # Direct mode is server-to-server (internal app token) — no per-user token
    # needed. Proxy mode still needs the user's gateway access_token.
    if settings.XTS_MODE != "direct" or not settings.has_app_credentials():
        token = access_token or os.getenv("XTS_ACCESS_TOKEN")
        if not token:
            raise HTTPException(400, "XTS access_token required (query or XTS_ACCESS_TOKEN env).")
    else:
        token = None

    adapter = build_adapter(access_token=token)
    try:
        try:
            adapter.login()
        except TokenError as e:
            raise HTTPException(503, f"XTS token unavailable: {e}")

        # Resolve segment/kind from the instrument master (falls back to static).
        meta = find_live(underlying, adapter)
        seg = segment or meta.get("segment", 2)
        kind = meta.get("kind", "stock")

        exp = expiry or adapter.nearest_expiry(underlying, seg)
        if not exp:
            raise HTTPException(404, f"no option expiries found for {underlying}")
        available = adapter.list_expiries(underlying, seg)

        instruments = adapter.list_option_instruments(underlying, exp, seg)
        if not instruments:
            raise HTTPException(404, f"no option instruments for {underlying} {exp}")

        strikes = sorted({i.strike for i in instruments if i.strike is not None})
        if not strikes:
            raise HTTPException(404, f"no strikes parsed for {underlying} {exp}")

        # Underlying quote (ltp + session VWAP): equity for stocks, front future
        # for indices. Also gives a real spot (better than the parity estimate).
        spot_vwap = None
        spot_ltp = None
        spot_prev_close = None
        spot_bars = []
        if hasattr(adapter, "spot_quote"):
            sq = adapter.spot_quote(underlying, kind, seg)
            if sq:
                spot_ltp = sq.ltp or None
                spot_vwap = sq.vwap or None
                spot_prev_close = sq.prev_close or None
            # The quote's Close becomes TODAY's close after the session ends;
            # daily bars give the true previous session close in every state.
            if hasattr(adapter, "spot_instrument"):
                si = adapter.spot_instrument(underlying, kind, seg)
                if si:
                    try:
                        spot_bars = adapter.daily_bars(si, days=40)
                    except Exception:  # noqa: BLE001
                        spot_bars = []
                    if len(spot_bars) >= 2:
                        spot_prev_close = spot_bars[-2]["close"]

        # Reference price to centre the strike window (best-effort).
        ref = spot or spot_ltp or adapter.reference_price(underlying, kind, exp, seg)
        if ref:
            center = ref
        else:
            # Pass A: sample ~15 strikes across the range to find rough ATM via
            # put-call parity. Uses a throwaway store (no baseline pollution).
            step = max(1, len(strikes) // 15)
            sample = set(strikes[::step])
            sample_ins = [i for i in instruments if i.strike in sample]
            sample_q = adapter.fetch_touchline_for(sample_ins)
            sample_snap = SnapshotStore().build_chain(
                underlying=underlying, spot=0, expiry=exp,
                instruments=sample_ins, quotes=sample_q,
            )
            center = estimate_spot_from_chain(sample_snap.rows) or strikes[len(strikes) // 2]

        # Baseline preference:
        #  1. previous session's closing OI from daily candles — the same basis
        #     NSE uses for "Chng in OI"; works even when the market is closed;
        #  2. persisted market-open baseline;
        #  3. intraday first-sighting (weakest — not a true day ΔOI).
        store = _LIVE_STORE
        baseline_kind = "day-open" if _BASELINE.is_fresh() else "intraday"

        # Pass B: window of N strikes nearest the centre, BOTH legs per strike.
        near = set(sorted(strikes, key=lambda s: abs(s - center))[:max_strikes])
        keep = [i for i in instruments if i.strike in near]
        # Direct mode fetches real OI (batch); proxy mode is touchline-only.
        if getattr(adapter, "supports_oi", False):
            quotes = adapter.fetch_quotes_for(keep)
        else:
            quotes = adapter.fetch_touchline_for(keep)

        # Prefer previous-close OI as the ΔOI baseline (matches NSE, works after hours).
        if not _BASELINE.is_fresh() and hasattr(adapter, "previous_close_oi"):
            try:
                prev = adapter.previous_close_oi(keep)
            except Exception:  # noqa: BLE001 — history is best-effort
                prev = {}
            if len(prev) >= max(2, len(keep) // 2):
                store = SnapshotStore()          # isolated: seeded with prev-close OI
                for ins in keep:
                    if ins.instrument_id in prev:
                        store.set_baseline(ins.segment, ins.instrument_id, prev[ins.instrument_id])
                baseline_kind = "prev-close"

        snap = store.build_chain(
            underlying=underlying, spot=ref or 0, expiry=exp,
            instruments=keep, quotes=quotes,
            strike_interval=meta.get("strike"),
        )

        # Spot: explicit -> underlying LTP -> parity on the window -> centre.
        if spot:
            spot_source = "provided"
        elif spot_ltp:
            snap.spot = spot_ltp
            spot_source = "future" if kind == "index" else "equity"
        else:
            est = estimate_spot_from_chain(snap.rows)
            snap.spot = est or center
            spot_source = "parity_estimate" if est else "atm_guess"

        oi_ok = chain_has_oi(snap)
        has_delta = any(r.call.change_oi or r.put.change_oi for r in snap.rows)
        baseline_fresh = _BASELINE.is_fresh()
        result = verdict_to_dict(analyze(
            snap, spot_vwap=spot_vwap, spot_ltp=spot_ltp,
            spot_prev_close=spot_prev_close,
            # ΔOI is only the document's "change vs previous close" when it is
            # measured against a real market-open baseline.
            delta_is_day_open=baseline_kind in ("prev-close", "day-open"),
            bars=spot_bars,
        ))
        result["expiry_used"] = exp
        result["available_expiries"] = available
        result["spot_source"] = spot_source
        # OI/volume are reported in CONTRACTS (lots), matching the NSE chain.
        result["lot_size"] = next((getattr(i, "lot_size", 1) for i in keep), 1)
        result["oi_unit"] = "contracts"
        if not oi_ok:
            note = (
                "LIMITED: no per-strike Open Interest available, so ΔOI classification, "
                "PCR and conversion are unavailable — premium-direction read only."
            )
        elif baseline_kind == "prev-close":
            note = ("Full SOP live: Change-in-OI is measured against the PREVIOUS SESSION's "
                    "closing OI — the same basis NSE uses — so it is valid even after hours.")
        elif baseline_kind == "day-open":
            note = ("Full SOP live: Change-in-OI measured against today's market-open baseline.")
        elif has_delta:
            note = ("Live OI with intraday Change-in-OI only (baselined from the first snapshot "
                    "this session) — not a true day ΔOI.")
        else:
            note = ("Live OI is flowing: OI walls and PCR are real, but Change-in-OI is not yet "
                    "available for this chain.")
        result["data_quality"] = {
            "oi_available": oi_ok,
            "delta_oi_available": has_delta or baseline_fresh,
            "baseline": baseline_kind,
            "spot_source": spot_source,
            "note": note,
        }
        return result
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        raise HTTPException(502, f"live feed error: {e}")

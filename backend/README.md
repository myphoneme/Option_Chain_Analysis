# Option Chain SOP Engine — Backend

Phase-1 backend for the Option Chain Analysis app. Implements the **Professional
Scanning Sequence** (Module 5, Lesson 1) as an executable decision engine, plus
the XTS feed adapter wired to the phoneme QuantTrade gateway.

## What's built

| Layer | Module | Status |
|---|---|---|
| Domain models | `app/engine/models.py` | ✅ |
| Step 4 — Change-in-OI classification (8 labels) | `app/engine/classify.py` | ✅ |
| Steps 5–6 — PCR scorecards + OI-to-Volume | `app/engine/pcr.py` | ✅ |
| Steps 1–9 — SOP orchestrator → Verdict | `app/engine/sop.py` | ✅ |
| Step 8 — strategy selection | `app/engine/strategy.py` | ✅ |
| Feed abstraction | `app/feed/base.py` | ✅ |
| XTS adapter (gateway) | `app/feed/xts.py` | ✅ |
| ΔOI snapshot store + chain builder | `app/snapshot/store.py` | ✅ |
| FastAPI surface | `app/main.py` | ✅ |
| Golden-fixture tests (2 case studies) | `tests/` | ✅ 15 passing |

## Quick start

```bash
cd backend
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q            # 15 passing

# run the API
.venv/bin/uvicorn app.main:app --reload
# → http://127.0.0.1:8000/docs
```

## Endpoints

- `GET /health`
- `GET /demo/nifty` · `GET /demo/banknifty` — run the engine on the document's
  case studies (offline; no feed needed). Reproduces the exact PCRs & verdict.
- `POST /analyze` — analyze a client-supplied chain snapshot (see `ChainIn`).
- `GET /live/verdict` — build a live chain from XTS and analyze it (needs a
  gateway `access_token`).

## Live smoke test (market hours)

```bash
XTS_ACCESS_TOKEN=<gateway token> \
.venv/bin/python scripts/live_smoke.py NIFTY 25AUG2026 24200 --strikes 5
```

## Why the golden tests matter

The engine is validated against the two worked examples in the lesson:

- **NIFTY** (spot 24,201.90): Total-OI PCR 1.22, ΔOI-PCR 2.47, Vol-PCR 0.70,
  CE conv 4.6%, PE conv 16.2% → **BULLISH**, support 24,200, invalidation below.
- **BANKNIFTY** (spot 58,014.20): Total-OI PCR 0.88, ΔOI-PCR 6.16, Vol-PCR 0.79,
  CE conv 2.2%, PE conv 16.8% → **BULLISH**, support 58,000.

Every number is asserted against the document. If a refactor breaks the math,
CI catches it.

## Live mode (direct XTS via internal token)

Set in `backend/.env` (gitignored):

```
XTS_APP_KEY=qt_key_...
XTS_APP_PASSWORD=qt_app_...
XTS_MODE=direct
BASELINE_AUTOCAPTURE=true      # optional: auto-capture baseline at 09:16 IST
```

The backend gets a short-lived XTS token (Basic Auth → `/api/internal/xts/marketdata/token`)
and calls XTS directly at ttblaze (batch quotes incl. **real OI**). Instrument discovery uses
the XTS instrument master (cached daily). No per-user token needed.

## Market-open OI baseline (enables full Change-in-OI)

XTS gives only *current* OI. The SOP's Change-in-OI needs a previous-close baseline, so we
snapshot OI at market open and diff against it:

```bash
# capture now (start using today) — or schedule at 09:16 IST via cron
.venv/bin/python scripts/capture_baseline.py                 # default tracked set
.venv/bin/python scripts/capture_baseline.py NIFTY BANKNIFTY
# or trigger over HTTP
curl -X POST "http://localhost:8000/admin/baseline/capture?underlyings=NIFTY,BANKNIFTY"
curl http://localhost:8000/admin/baseline/status
```

Cron (weekdays, 09:16 IST):
```
16 9 * * 1-5  cd /path/backend && .venv/bin/python scripts/capture_baseline.py >> baseline.log 2>&1
```

With `BASELINE_AUTOCAPTURE=true`, the app runs the capture itself at 09:16 IST (daemon thread,
weekend-aware). The baseline persists to `data/oi_baseline.json` (keyed by trade date), so it
survives restarts and is shared by every request that day. `data_quality.baseline` in the
verdict reports `day-open` / `intraday` / `none`.

## Known gateway dependencies (from the live audit)

The live path needs these gateway fixes (tracked in the product blueprint):
1. **Shared XTS session** server-side (single-session token); the adapter already
   retries on `Invalid Token`, but concurrent per-request logins will still thrash.
2. **Batch quote + expiry/strike enumeration** endpoints — until then the chain is
   fetched serially (~200 ms/instrument), so keep strike counts modest.
3. **ΔOI**: XTS gives current OI only. `SnapshotStore` computes Change-in-OI by
   diffing against a day baseline. Seed the baseline at market open for true
   day-ΔOI; otherwise it measures intraday ΔOI from first sighting.

## Next slices (per blueprint)

- Persist snapshots (TimescaleDB) + Redis hot cache; scheduled OI refresh worker.
- IV (Black-Scholes solve) and IV-rank columns.
- Next.js frontend: live chain grid + Verdict Card with the 9-step evidence.
- Conviction screener across the F&O universe.

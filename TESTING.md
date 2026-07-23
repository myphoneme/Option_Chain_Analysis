# Testing Guide — Option Chain SOP Analyzer

Test in layers, cheapest first. Tiers 1–2 need nothing. Tiers 3+ need the live
gateway (creds in `backend/.env`, `ENABLE_INTERNAL_XTS_TOKEN_API=true`) and are
best run **during market hours (09:15–15:30 IST)**.

Assumes: `cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`.

---

## Tier 1 — Automated unit tests (no market, no creds)

```bash
cd backend && .venv/bin/python -m pytest -q      # 27 tests, ~0.1s
```

This is the correctness anchor. The golden fixtures reproduce the **two worked
case studies from the document exactly** (NIFTY PCR 1.22/2.47/0.70 → BULLISH;
BANKNIFTY 0.88/6.16/0.79). If a change breaks the math, these fail. Also covers:
the 8-label classification matrix, negative-ΔOI robustness, the XTS parsers
(against real captured payloads), the token provider (404/401 handling), and the
baseline store.

**Pass criteria:** all green.

---

## Tier 2 — Offline engine via the API (no creds)

```bash
.venv/bin/uvicorn app.main:app --port 8000        # terminal 1
curl -s localhost:8000/demo/nifty | python3 -m json.tool | head -40
curl -s localhost:8000/demo/banknifty | python3 -m json.tool | head -40
```

**Pass criteria:** `/demo/nifty` returns `bias: BULLISH`, `pcr.total_oi_pcr ≈ 1.22`,
`change_oi_pcr ≈ 2.47`; `/demo/banknifty` returns `6.16`. These prove the full
9-step pipeline + serialization without any feed. Also try a hand-built chain:

```bash
curl -s -X POST localhost:8000/analyze -H 'Content-Type: application/json' -d '{
 "underlying":"TEST","spot":100,"strike_interval":5,
 "rows":[{"strike":100,"call":{"premium_change":5,"change_oi":10000,"oi":10000,"volume":100000},
                       "put":{"premium_change":-5,"change_oi":30000,"oi":30000,"volume":90000}}]}' | python3 -m json.tool
```

---

## Tier 3 — Live plumbing (market hours, creds required)

```bash
# 1. token flow works?
curl -s -X POST "https://quantapi.phoneme.in/api/internal/xts/marketdata/token" \
  -u "$XTS_APP_KEY:$XTS_APP_PASSWORD" -w "\n[HTTP %{http_code}]\n"     # expect 200 + token

# 2. capture the day-open baseline (do this right after 09:15)
curl -s -X POST "localhost:8000/admin/baseline/capture?underlyings=NIFTY,BANKNIFTY" | python3 -m json.tool
curl -s localhost:8000/admin/baseline/status                            # fresh:true, count>0

# 3. run a live verdict
curl -s "localhost:8000/live/verdict?underlying=NIFTY&max_strikes=11" | python3 -m json.tool
```

**Pass criteria:** verdict returns 200; `data_quality.oi_available:true`,
`data_quality.baseline:"day-open"`; `pcr.total_oi_pcr` is a real number; spot/ATM/
expiry look sane. Right after capture, classifications may be `Neutral` (OI hasn't
moved yet) — re-run a few minutes later and Change-in-OI labels should appear.

---

## Tier 4 — Correctness cross-check (the important one)

The engine can be internally consistent but still wrong if the *feed* is wrong.
Validate against an independent reference you trust:

1. Pick **NIFTY, ATM strike**, note the time.
2. Open the same chain in **your broker / Sensibull / NSE option-chain** at the
   same moment.
3. Compare, for 3–4 strikes around ATM:
   - **LTP, OI, Volume** — should match (allow for NSE's ~3-min OI refresh lag).
   - **Total-OI PCR at ATM** — should be within rounding.
   - **Change-in-OI direction** — app's ΔOI sign must agree with NSE's "Chng in OI".
   - **Classification label** — if NSE shows a strike's PE premium falling while
     PE OI rises, the app must label it **Put Writing** (and so on for the matrix).

**Pass criteria:** OI/LTP/volume match the reference; labels and PCR agree in
direction and magnitude. Disagreement here points at the feed or the baseline,
not the engine.

> Note: the app's baseline is captured at 09:15, so its ΔOI is measured vs the
> open. A reference that measures vs *previous close* will differ slightly before
> 09:15 activity — compare late morning onward for the cleanest match.

---

## Tier 5 — UI (frontend)

```bash
cd frontend && npm install && npm run dev          # localhost:3000
```

Click through:
- Search + pick an **index** (NIFTY) and a **stock** (RELIANCE) — verdict card,
  PCR scorecards, classification table (ATM highlighted, support/resistance),
  strategy + invalidation, 9-step evidence trail all render.
- **Expiry selector** appears after a live run; switching it re-runs the analysis.
- **Banner** reads "Live · full SOP" (green) when a day-open baseline exists,
  "Live · OI active" (blue) intraday, "Live · limited" (amber) if OI missing.
- Case-study entries (offline) always work and match the document.

---

## Tier 6 — Robustness / edge cases

- **After hours:** run a live verdict → should still return (stale LTPs, parity
  spot), never crash.
- **Invalid symbol:** `?underlying=NOTASYMBOL` → clean 404/empty, not a 500.
- **Illiquid stock / thin strikes:** fetch tolerates missing quotes (skips them).
- **Restart persistence:** capture baseline → restart uvicorn → run verdict →
  `baseline:"day-open"` still (loaded from `data/oi_baseline.json`).
- **Expiry switch:** pick a far expiry → chain + verdict recompute for it.

---

## Tier 7 — Operational / daily & strategy validation

- Set `BASELINE_AUTOCAPTURE=true`; next trading day after 09:16 confirm
  `GET /admin/baseline/status` shows `fresh:true` without manual capture.
- Spot-check the same script at 10:00, 12:00, 14:00 — verdict/ΔOI should evolve
  as positions build.
- **Strategy edge (the real test over weeks):** log each non-"No Trade" verdict
  with its invalidation level, then compare to the actual move next session. Track
  hit-rate. This validates the *SOP*, not just the software. (Paper-trade first.)

---

## Quick "is it healthy right now" smoke

```bash
curl -s localhost:8000/health
curl -s localhost:8000/meta                        # xts_mode, needs_user_token
curl -s localhost:8000/admin/baseline/status
curl -s "localhost:8000/live/verdict?underlying=NIFTY" | python3 -c \
  'import sys,json;d=json.load(sys.stdin);print(d.get("bias"),d.get("data_quality",{}).get("baseline"))'
```

# Option Chain SOP Analyzer

Decision-support app that runs the **Professional Scanning Sequence** (Module 5,
Lesson 1) over live NSE/BSE option chains and drafts a trade verdict — bias,
suggested strategy, invalidation level, and the 9-step evidence behind it.

## Structure

| Path | What |
|---|---|
| `backend/` | FastAPI SOP engine + XTS feed (direct via internal token) + market-open OI baseline. See `backend/README.md`. |
| `frontend/` | Next.js UI — searchable F&O picker, verdict card, PCR, ΔOI classification, evidence trail. See `frontend/README.md`. |
| `Product_Blueprint_Option_Chain_App.md` | Product/market/architecture blueprint. |
| `Gateway_Option_Chain_Endpoint_Spec.md` | Gateway API notes for the data team. |
| `TESTING.md` | Layered test plan (unit → live → correctness cross-check). |

## Quick start

```bash
# backend
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # fill in XTS_APP_KEY / XTS_APP_PASSWORD
.venv/bin/python -m pytest -q # 27 tests
.venv/bin/uvicorn app.main:app --port 8000

# frontend (new terminal)
cd frontend && npm install && npm run dev   # http://localhost:3000
```

## Live data

Direct XTS via a short-lived internal token (Basic Auth → gateway). Needs
`ENABLE_INTERNAL_XTS_TOKEN_API=true` on the gateway and the app credential scoped
`xts:marketdata:token`. Set `BASELINE_AUTOCAPTURE=true` to snapshot the day-open
OI baseline at 09:16 IST (enables full Change-in-OI classification).

> Educational analysis, not investment advice. Verdicts always include an
> invalidation level and a "No Trade" state.

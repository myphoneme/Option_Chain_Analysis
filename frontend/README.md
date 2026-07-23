# Option Chain SOP Analyzer — Frontend

Next.js 14 (App Router) + TypeScript + Tailwind UI for the SOP engine.

## Run

```bash
# 1. start the backend (separate terminal)
cd ../backend && .venv/bin/uvicorn app.main:app --port 8000

# 2. start the frontend
cd frontend
npm install
npm run dev            # http://localhost:3000
```

Set `NEXT_PUBLIC_API_BASE` if the backend isn't on `http://localhost:8000`.

## Flow

Select a script → **Run SOP Analysis** → the full Professional Scanning
Sequence is drafted:

- **Verdict card** — bias, confidence bar, spot/ATM/support/resistance
- **PCR scorecards** — Total-OI, Change-in-OI, Volume PCR + CE/PE conversion
- **Classification table** — the 8-label Change-in-OI matrix per strike, ATM
  highlighted, support/resistance zones tagged
- **Strategy & invalidation** — trader-type actions + the level that voids the view
- **9-step evidence trail** — why the verdict, step by step

## Components

`components/` — `ScriptSelector`, `VerdictCard`, `PcrScorecard`,
`ClassificationTable`, `StrategyList`, `EvidenceTrail`.
`lib/api.ts` — backend client (`/scripts`, `/demo/{id}`, `/live/verdict`).

## Status

Wired to `/demo/{nifty,banknifty}` (works offline; reproduces the case studies).
The live path (`/live/verdict`) is ready in `lib/api.ts` and unlocks when the
gateway restores per-strike OI/volume (see product blueprint re-audit).

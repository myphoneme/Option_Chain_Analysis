# Option Chain Analysis App — Product Blueprint
**Based on:** Final_Module_5_Lesson_1 (Professional Option Chain Analysis SOP)
**Scope:** NSE, BSE and MCX option segments | Prepared: 13-Jul-2026

---

## 1. What the App Does (Product Definition)

The app is a **decision-support engine** that executes the document's 9-step Professional
Decision Template automatically for any F&O script, in real time, and outputs a
**Verdict Card**: directional bias, confidence, suggested strategy, and a pre-defined
invalidation level — including the "No Trade" verdict, which is the SOP's core discipline.

### The SOP as an algorithm (engine specification)

| Step | Checkpoint (from the document) | Engine implementation |
|---|---|---|
| 1 | Spot & ATM | Auto-detect spot; snap to nearest strike per instrument's strike interval |
| 2 | Premium direction | Compare CE/PE premium change across ATM ± N strikes → bullish / bearish / mixed |
| 3 | Top OI zones | Rank strikes by Call OI (resistance candidates) and Put OI (support candidates) |
| 4 | Change-in-OI classification | Apply the 4-label matrix per strike: Call Long Build-up (CE↑ premium, CE↑ OI), Call Writing (CE↓ premium, CE↑ OI), Put Long Build-up (PE↑, OI↑), Put Writing (PE↓, OI↑) + unwinding/short-covering variants |
| 5 | PCR scorecards | Total OI PCR = PutOI/CallOI; Change-in-OI PCR = fresh PE OI / fresh CE OI; Volume PCR = PutVol/CallVol — at ATM and key strikes |
| 6 | Volume conversion | Conversion % = ΔOI / Volume per side → churn vs conviction flag |
| 7 | Support/Resistance confirmation | Accept a level only when OI, ΔOI, premium behaviour and PCR agree |
| 8 | Strategy selection | Map verdict → strategy menu (directional CE/PE buy ATM/slight-ITM, Bull Put Spread, Bear Call Spread, range strategies, or **No Trade**) |
| 9 | Invalidation | Compute the level where the view breaks (e.g., support strike break + PE OI unwinding + PE premium rising) and display it before entry |

**Golden test fixtures:** the two worked case studies in the document (NIFTY spot 24,201.90,
ATM 24,200, ΔOI-PCR 2.47; BANKNIFTY spot 58,014.20, ATM 58,000, ΔOI-PCR 6.16) should be
encoded as regression tests — the engine must reproduce those exact inferences.

---

## 2. Market Analysis

### Competitive landscape (India, 2026)

| Product | Strength | Price | Weakness vs. our SOP approach |
|---|---|---|---|
| **Sensibull** | Beginner-friendly, strategy builder, payoff charts, 6-broker execution; free for Zerodha users | Free–Pro | Shows data & strategies; does not run an opinionated step-by-step verdict with invalidation discipline |
| **Opstra (Definedge)** | IV charts, backtesting, historical analytics | ~₹1,300/mo | Advanced-user oriented; no guided SOP; weak commodity coverage |
| **Quantsapp** | Greeks depth, build-up heatmaps, 250M+ strategy combinations, mobile-first | ~₹3,250/mo | Expensive; analytics-dense but not pedagogical; no "why" narrative |
| **NiftyTrader / free OI sites** | Free OI & PCR charts | Free | Index-centric, ad-heavy, no verdict, no MCX |
| **Broker built-ins (Dhan, Fyers, Upstox)** | Free, integrated execution | Free | Generic chain display; no classification engine |

### Gaps = our differentiation
1. **Opinionated verdict, not just data.** Every competitor shows OI/PCR; almost none walks
   the full sequence and outputs a defended conclusion *with an invalidation level* and an
   explicit **No-Trade** state.
2. **Explainability.** Each verdict expands into the exact 9 checkpoints with the live numbers —
   the app *teaches while it analyses* (education-first tools convert well in India's fast-growing
   retail F&O population).
3. **MCX coverage.** Crude, Natural Gas, Gold, Silver options volumes are surging and are
   badly served by existing chain-analysis tools — a genuine wedge.
4. **Conviction screener.** Run the SOP across all ~190 NSE F&O stocks + indices + MCX and
   rank by conviction score (agreement across steps). Nobody offers "which script has the
   cleanest option-chain story right now."
5. **Honest churn detection.** OI-to-Volume conversion % as a first-class metric is rare in
   retail tools.

### Target segments
- **Primary:** active retail index-options traders (NIFTY/SENSEX weekly expiries) — largest, most engaged cohort.
- **Secondary:** stock-options swing traders; MCX commodity options traders (underserved).
- **Tertiary:** trainers/academies (white-label the SOP dashboard as a teaching tool — the course itself is a distribution channel).

### Monetisation
Freemium: index chains + delayed stock data free; Pro (₹800–1,500/mo, undercutting Opstra/Quantsapp)
for real-time full-universe screener, alerts, MCX, replay & backtest. Broker referral/execution
revenue as a second line.

---

## 3. Feature Set

### MVP (Phase 1 — NIFTY, BANKNIFTY, SENSEX only)
- Live option chain with ATM auto-highlight, expiry selector
- Premium-direction panel (ATM ± 3 strikes, colour-coded)
- ΔOI classification labels on every strike (Long Build-up / Writing / Unwinding / Short Covering)
- Three PCR scorecards + OI-to-Volume conversion %
- **Verdict Card**: bias, strategy suggestions with payoff diagram, invalidation level, "No Trade" state
- OI bar chart (support/resistance walls), Max Pain
- 3–5 min snapshot history (intraday ΔOI timeline)

### Phase 2 — Breadth & retention
- All NSE stock options + BSE (SENSEX/BANKEX) + **MCX options**
- Conviction Screener across the full F&O universe, sortable by SOP score
- Alerts: PCR threshold cross, writing unwind at support, fresh build-up at watched strike, verdict flip (push / Telegram / WhatsApp)
- Watchlists; IV Rank/Percentile, IV skew, straddle-price chart
- Multi-expiry view; event calendar (expiry days, results, RBI/Fed)
- Intraday **replay mode** (scrub through the day's snapshots — powerful learning tool)

### Phase 3 — Stickiness & pro tools
- Paper trading + trade journal auto-filled from the Verdict Card (thesis, invalidation, outcome)
- Historical backtest: "how did the SOP verdict perform over the last N expiries?"
- Broker integration (Kite / Dhan / Fyers / Upstox) for one-click defined-risk spread execution with margin check
- Greeks columns & portfolio Greeks; position-size / risk calculator
- AI narrative layer: plain-language (English + Hindi) explanation of the day's chain story, generated from the engine's structured output — never freeform speculation
- Mobile apps (start as PWA, then native)

### Compliance features (build in from day one)
- Prominent disclaimers; no guaranteed-return language anywhere (SEBI-prohibited)
- "Educational analysis, not investment advice" framing; user acknowledgement flow
- **Legal checkpoint:** an app issuing buy/sell suggestions may fall under SEBI **Research Analyst (RA)** regulations; if Phase-3 adds one-click execution, SEBI's **algo-trading framework (mandatory from Apr-2026)** applies — Algo-ID per order, broker-routed, white-box logic disclosure. Engage a SEBI compliance counsel before public launch; RA registration is the likely requirement for the verdict feature.

---

## 4. Data Strategy (the make-or-break decision)

### Realities to design around
- **Scraping nseindia.com is not viable for a commercial product** — ToS prohibits commercial reuse, endpoints are aggressively rate-limited/blocked, and the public site data is delayed ~3 min anyway. Fine for prototyping only.
- **OI is not tick-by-tick.** Exchanges disseminate OI on a periodic refresh (~3 min on NSE). Premiums/quotes stream tick-by-tick. So: stream LTP/bid/ask/volume continuously, recompute the ΔOI classification and PCRs on each OI refresh. This drastically lowers the "high-frequency" burden — the SOP engine runs on a ~1–3 min cadence; the chain display updates in near-real-time.
- **Redistribution licensing:** displaying real-time exchange data to *your* users makes you a data redistributor — you need an authorized-vendor agreement and exchange approvals; delayed data (3–15 min) is far cheaper to license. Budget for this.

### Recommended providers (phased — XTS first)
| Stage | Source | Notes |
|---|---|---|
| Development + closed beta | **XTS Market Data API (via IIFL / Symphony Fintech)** | REST + Socket.IO WebSocket; TouchLine (1501), MarketDepth (1502), Candle (1505), **OpenInterest (1510)**, LTP (1512) events; covers NSE cash/F&O, BSE, MCX. Retail API keys are licensed for the account-holder's own use — keep the beta closed and small |
| Production (>100 users / paid launch) | **TrueData** or **Global Datafeeds** — authorized NSE + BSE + MCX vendors with redistribution tiers | Displaying live data to paying users makes you a redistributor; vendor agreement required at commercial launch regardless of user count |
| Fallback | Second vendor on standby | Feed redundancy; contract tests against both schemas |

### XTS integration notes
- **Latency:** no official figure published; in practice a broker-mediated internet WebSocket
  delivers touchline in roughly **100–300 ms** from exchange (server in India). Exchange retail
  broadcast is itself snapshot-based (multiple snapshots/sec), and OI updates arrive on the
  exchange's periodic refresh — both far faster than this app needs (UI ~1 s, SOP engine ~1–3 min).
- **Daily auth token** — re-login each morning before pre-open; automate it.
- **Instrument master** must be downloaded daily (symbols/tokens change with new expiries/strikes).
- **Subscription caps per AppKey** — quote-mode subscriptions are limited (configurable via
  dashboard); a full NIFTY + BANKNIFTY chain fits easily, the full F&O universe does not.
  Full-universe screener needs Broadcast-mode binary feed (institutional arrangement) or the
  Phase-2 vendor.
- **Socket.IO version pinning** — XTS uses an older Socket.IO protocol; pin `python-socketio`
  to the compatible major version and build robust auto-reconnect + resubscribe logic.
  Disconnects mid-session are a known reality; treat reconnect handling as a first-class feature.
- **Feed-adapter abstraction:** implement a `FeedAdapter` interface (subscribe, quotes stream,
  OI stream, instrument master) with `XTSAdapter` now and `TrueDataAdapter`/`GFDLAdapter` later —
  the migration at >100 users then becomes a config change, not a rewrite. Normalise everything
  to an internal tick/snapshot schema at the ingestion boundary.

### Live audit of quantapi.phoneme.in gateway (13-Jul-2026, market hours)
**Verified working:** app auth; XTS marketdata login via server-stored keys (userID PHONEME1,
app expiry 30-Dec-2026); instrument search (NSEFO OPTIDX incl. weekly/monthly strikes);
quote endpoint with Touchline 1501 (LTP, bid/ask + size/orders, volume, OHLC, %chg) and
**OpenInterest 1510** (per-strike OI + UnderlyingTotalOpenInterest); BSE FO (SENSEX futures)
reachable. Latency for full gateway round trip: **median ~215 ms, p90 ~245 ms**.

**Issues found (fix list):**
1. **XTS single-session:** every `marketdata/login` invalidates the previous token → server must
   hold ONE shared md-session (refresh on schedule / on auth failure), never login per request.
2. **Stateless wrapper:** `quote`/`symbol` require the md-token in the request body; gateway
   should inject the shared token server-side instead.
3. **No chain endpoints:** missing expiry list, strike enumeration, and batch quote (XTS native
   quotes API accepts an instrument list — proxy it). A 50-strike chain via single quotes at
   ~215 ms/call is ~40 s serial; batch or parallelise.
4. **MCX absent:** segment-51 search returns no commodity contracts, and the search endpoint
   ignores `exchangeSegment` (returns NSE equities stamped with the requested segment id — bug).
   Confirm with IIFL whether the key includes MCX; if not, MCX needs Phase-2 vendor.
5. **No ΔOI / IV:** compute server-side (OI snapshot job + Black-Scholes IV) as planned.
6. **SECURITY — cross-user data leak:** `/api/xts/stream` (SSE) streams ALL broker accounts'
   names, P&L and holdings to any authenticated user regardless of ownership. Add per-user
   authorization filtering before anything else.
7. **Open registration** on `/api/auth/register` — gate before launch.
8. `/api/analysis/scan` returns placeholder values (RSI 50.0, price null) and takes ~10 s — needs
   real implementation and caching.

### Gateway update re-audit (14-Jul-2026)
The gateway was revised between audits. **Fixed:** `marketdata/login` now holds the XTS session
**server-side** (returns `marketdataToken:true`, no client token) — resolves issues #1 and #2 above;
a 2s quote cache (`quoteCacheTtlSeconds`) was added. **Regression that now blocks the app:**
`marketdata/quote` was simplified to return **only `{ltp, close}`** and ignores `xtsMessageCode` —
so **Open Interest, volume and bid/ask are no longer returned**. Premium direction still works
(LTP − close), but ΔOI, PCR and the OI-to-Volume conversion — the heart of the SOP — cannot be
computed from live data until this is restored.
**Required gateway change:** either restore the rich touchline+OI fields on `marketdata/quote`, or
(preferred) add a dedicated **`/api/xts/option-chain?underlying&expiry`** endpoint returning all
strikes with CE/PE LTP, bid, ask, volume and OI in one call (also solves the batch-quote gap).
The backend `XTSAdapter` already parses both the old rich format and the new simple one, so it will
work unchanged the moment OI is available again.
**Security items #6 (cross-user stream leak) and #7 (open registration) remain unfixed** as of this
re-audit.

---

## 5. Technical Stack

### Architecture (event-driven, snapshot-based)

```
Vendor WS feed ─► Ingestion workers ─► Message bus ─► Analytics engine ─► Snapshot store
 (TrueData/GFDL)   (normalize ticks)    (Redis Streams     (SOP steps 1-9      (TimescaleDB)
                                         → Kafka at scale)   per underlying)         │
                                                                  │                  ▼
User ◄── WebSocket gateway ◄── Redis pub/sub + cache ◄────────────┴──── REST API (FastAPI)
```

| Layer | MVP choice | Scale-up path | Why |
|---|---|---|---|
| Ingestion | **Python asyncio** workers | Go workers | Vendor SDKs are Python-first; asyncio easily handles L1 WS volumes |
| Message bus | **Redis Streams** | Kafka / Redpanda | Redis is enough until you stream the full F&O universe to thousands of users |
| Analytics engine | **Python + Polars/NumPy** | Same, horizontally sharded by underlying | Vectorised chain math; stateless workers keyed on (underlying, expiry) |
| Time-series store | **TimescaleDB** (Postgres ext.) | ClickHouse for heavy replay/backtest queries | One database for snapshots *and* relational data (users, watchlists) at MVP |
| Hot cache | **Redis** (last snapshot + verdicts) | Redis Cluster | Sub-ms reads for the WS gateway |
| API | **FastAPI** (REST + WS) | Split WS fan-out into its own gateway service | Python end-to-end keeps the team small |
| Frontend | **Next.js + React + TypeScript**, TanStack Table (virtualised), ECharts / TradingView Lightweight Charts, Tailwind | React Native or Flutter for native mobile; PWA first | Virtualised grids are essential for 50-strike live chains |
| Auth & billing | Self-hostable auth (Keycloak / Supabase self-hosted) + **Razorpay** subscriptions | — | India-native payments (UPI, cards); no dependency on managed cloud auth |
| Infra | **Private cloud** — Docker Compose on 2–3 VMs at MVP | k3s/Kubernetes cluster on private cloud; capacity plan for market-hours peak (no elastic autoscale) | Everything in this stack is self-hostable by design |
| IaC / Observability | Terraform/Ansible; Prometheus + Grafana + Loki; self-hosted Sentry (or GlitchTip); feed-lag & verdict-latency SLO dashboards | — | "Feed staleness" is your #1 production alert |

**Private-cloud specifics:**
- **Network path matters more than compute:** ensure low-latency, reliable outbound internet
  from the data-centre to the XTS endpoint (IIFL/Symphony servers, Mumbai). Dual ISP links if
  possible; the feed is your single most critical dependency.
- **No elastic autoscaling** — capacity-plan for the 09:15 open and 15:25 close spikes and for
  MCX evening session; keep ~2× expected peak headroom.
- **Self-hosted state:** TimescaleDB with streaming replication + nightly off-site backups;
  Redis with persistence (AOF) for the hot snapshot cache.
- **NTP discipline:** all snapshot timestamps must come from a synced clock — ΔOI windows and
  replay depend on it.
- **TLS/ingress:** Nginx or Traefik terminating WSS for client connections; WebSocket
  keep-alive tuning (proxy timeouts > heartbeat interval).

**Deliberate simplification:** start as a **modular monolith** (ingestion, engine, API as modules
in one deployable) with Redis + TimescaleDB. Split into services only when the screener across
the full universe or user concurrency forces it. Premature microservices will kill MVP velocity.

### Sizing reality check
Full NSE F&O universe ≈ ~200 underlyings × ~2–4 expiries × ~30–100 strikes × 2 sides ≈
**~10⁵ instruments**; L1 tick volumes are well within a single beefy ingestion node + Redis.
The engine recomputes on OI refresh (~3 min) — trivially parallelisable. This is *not* HFT
infrastructure; don't build it like HFT.

---

## 6. Agile Delivery Plan

### Team (lean)
1 product owner (you/domain expert), 2 backend, 1 frontend, 1 QA-automation (shared),
compliance counsel on retainer. Scrum, **2-week sprints**, trunk-based development,
feature flags for every user-visible feature.

### Roadmap
| Phase | Sprints | Outcome |
|---|---|---|
| 0 — Discovery | 1–2 | Vendor contracts, compliance opinion, engine spec frozen from the Lesson-1 doc, clickable Figma prototype |
| 1 — MVP | 3–8 | Index options (NIFTY/BANKNIFTY/SENSEX) live chain + Verdict Card; closed beta with ~50 traders from the course community |
| 2 — Breadth | 9–14 | Stock options, MCX, screener, alerts; public launch + Razorpay billing |
| 3 — Pro | 15+ | Replay, backtesting, paper trading, broker execution (post-RA/algo compliance) |

### Testing strategy (finance-specific)
1. **Golden-fixture unit tests** — encode both case studies from the document; every classification-matrix cell, all three PCR formulas, conversion %, and the final inference must match. These are your ground truth.
2. **Property-based tests** (Hypothesis) — e.g., OI never negative; the four OI outcomes table (new-new ↑, transfer →, close-close ↓) holds under random trade sequences.
3. **Replay testing** — record full market days from the vendor feed; replay them in CI at 100× speed and assert engine outputs are deterministic and stable. This is also your staging feed after hours.
4. **Contract tests** on the vendor schema — vendors change payloads without notice; fail fast in CI, not in production at 9:16 AM.
5. **Shadow validation** — during beta, auto-compare computed PCR/OI values against NSE EOD bhavcopy and one competitor's displayed values; alert on divergence > tolerance.
6. **Load tests** (k6/Locust) — WS fan-out at 5–10× expected concurrent users, specifically at 9:15 open and 15:25 close spikes.
7. **Chaos drills** — kill the vendor feed mid-session; UI must show "data stale since HH:MM" rather than silently freezing (a stale verdict is the most dangerous bug this product can have).
8. **UAT during live market hours** with real traders each sprint review.

### CI/CD & deployment discipline
- GitHub Actions: lint → unit → property → replay-subset → build → deploy to staging (fed by recorded replay).
- **Blue-green deploys, never during market hours** (NSE/BSE 09:15–15:30; MCX until 23:30/23:55 IST → deploy window is early morning or weekends).
- Canary: route 5% of WS sessions to the new version for one full session before promote.
- Feature flags + instant rollback; every release tagged with the engine version shown in the UI (traders must know which logic produced a verdict).
- Post-market automated smoke: replay today's session against yesterday's engine and diff verdicts.

---

## 7. Key Risks
| Risk | Mitigation |
|---|---|
| Data licensing cost/complexity | Start delayed-data free tier; real-time only for paid; negotiate vendor redistribution early |
| SEBI RA classification of "trade suggestions" | Legal opinion in Phase 0; educational framing; RA registration path budgeted |
| OI refresh latency misleading users | Show OI timestamp explicitly; never present stale ΔOI as live |
| Verdict overtrust by beginners | Always show invalidation level + the 9-step evidence; keep "No Trade" prominent |
| Vendor outage during market hours | Dual-vendor failover; staleness banners; status page |

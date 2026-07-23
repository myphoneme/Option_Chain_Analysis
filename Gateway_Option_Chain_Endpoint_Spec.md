# Gateway Spec: `/api/xts/option-chain` (and the OI regression)

**For:** the QuantTrade gateway team (quantapi.phoneme.in)
**From:** Option Chain SOP app
**Date:** 2026-07-14
**Priority:** P1 — blocks the core product (ΔOI classification, PCR, conversion)

---

## 1. Background / the problem

The app's SOP engine needs, **per strike**: Open Interest, previous-day OI (for
Change-in-OI), volume, LTP, previous close, best bid, best ask — for both CE and PE.

The current `POST /api/xts/marketdata/quote` was simplified and now returns only
`{ltp, close}` and **ignores `xtsMessageCode`**. So OI, volume and depth are no
longer reachable. Verified 2026-07-14:

```json
// POST /api/xts/marketdata/quote {"exchangeSegment":2,"exchangeInstrumentID":61492,"xtsMessageCode":1510}
{"ok":true,"response":{"result":{"ltp":183.45,"close":130.1, ...}}}   // no OpenInterest
```

Until this is fixed, every live verdict runs in degraded "premium-direction only"
mode. Two acceptable fixes — **Option A is strongly preferred.**

---

## 2. Option A (preferred): new batch option-chain endpoint

One call returns the whole chain, solving both the OI gap **and** the serial
fetch problem (today a 15-strike chain = ~60 sequential quote calls).

### Request

```
GET /api/xts/option-chain
  ?underlying=RELIANCE        # required, trading symbol
  &expiry=28JUL2026           # optional; nearest expiry if omitted
  &segment=2                  # optional; 2=NSEFO, 12=BSEFO, 51=MCXFO
  &strikes=15                 # optional; strikes centred on ATM (default all)
Cookie: access_token=<gateway JWT>
```

### Response

```json
{
  "ok": true,
  "underlying": "RELIANCE",
  "segment": 2,
  "expiry": "28JUL2026",
  "available_expiries": ["28JUL2026", "25AUG2026", "29SEP2026"],
  "spot": 1294.45,                 // underlying LTP (index/equity), if available
  "atm": 1290,
  "timestamp": "2026-07-14T14:41:07+05:30",
  "rows": [
    {
      "strike": 1290,
      "call": {
        "ltp": 24.6, "prev_close": 22.1, "bid": 24.4, "ask": 24.8,
        "volume": 431200, "oi": 1825600, "prev_close_oi": 1774900
      },
      "put": {
        "ltp": 20.15, "prev_close": 25.0, "bid": 19.9, "ask": 20.3,
        "volume": 388400, "oi": 2011300, "prev_close_oi": 1902100
      }
    }
  ]
}
```

### Field requirements (this is the crux)

| Field | Source (XTS) | Why the app needs it |
|---|---|---|
| `oi` | 1510 `OpenInterest` | OI walls, Total-OI PCR |
| `prev_close_oi` | previous session OI baseline | **Change-in-OI** = `oi - prev_close_oi` (the SOP core) |
| `volume` | 1501 `TotalTradedQuantity` | Volume PCR, OI-to-Volume conversion |
| `ltp`, `prev_close` | 1501 `LastTradedPrice`, `Close` | premium change = `ltp - prev_close` |
| `bid`, `ask` | 1501/1502 Bid/Ask | liquidity display |
| `spot` | underlying LTP | ATM detection (app currently parity-estimates this) |

> **`prev_close_oi` is the single most valuable addition.** Without it the app must
> snapshot OI at market open and diff — workable, but a day-open baseline from the
> gateway is far more reliable. If you can't provide it, at minimum restore live `oi`.

---

## 3. Option B (fallback): restore rich fields on `marketdata/quote`

If a new endpoint is too much, make `marketdata/quote` honour `xtsMessageCode`
again and pass through the full XTS payload:

- `1501` → `LastTradedPrice, Close, TotalTradedQuantity, BidInfo{Price}, AskInfo{Price}`
- `1510` → `OpenInterest, UnderlyingTotalOpenInterest`

The app's `XTSAdapter` already parses this rich format (it kept the old parser),
so Option B needs **zero app changes** — just restore the fields.

---

## 4. Compatibility

The app adapter (`app/feed/xts.py`) already:
- accepts the server-side session (`marketdata/login` → `marketdataToken:true`);
- parses **both** the old rich `listQuotes` format and the new simple `{ltp,close}`;
- flags `data_quality.oi_available=false` when OI is absent.

So whichever option ships, the app consumes it without a rewrite. For Option A we
add one `option-chain` method to the adapter (small).

---

## 5. Unrelated but still open (from the 13/14-Jul audits) — please also address

1. **SECURITY (P0): cross-user data leak.** `GET /api/xts/stream` streams *all*
   users' broker accounts (names, P&L, holdings) to any authenticated user. Must
   filter to the caller's own `user_id`.
2. **Open registration:** `POST /api/auth/register` is publicly reachable — gate it.
3. **MCX (segment 51):** search returns no commodity contracts and ignores the
   `exchangeSegment` filter (returns NSE equities). Confirm the key includes MCX.

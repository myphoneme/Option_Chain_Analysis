# SOP: Internal Access to QuantTrade XTS MarketData API

## 1. Purpose

QuantTrade keeps XTS MarketData credentials secure on the backend. Public web users never receive XTS app keys, secrets, or login tokens.

Trusted internal projects can use a QuantTrade-generated app credential to request an XTS MarketData login token over API, then use that token for XTS MarketData calls such as quote, symbol lookup, and instrument master.

## 2. Access Summary

Internal project receives:

```text
APP_KEY=qt_key_xxxxxxxxxxxxxxxxx
APP_PASSWORD=qt_app_xxxxxxxxxxxxxxxxx
```

Internal project uses those values to call:

```text
POST https://quantapi.phoneme.in/api/internal/xts/marketdata/token
```

QuantTrade returns:

```text
XTS_MARKETDATA_TOKEN
```

The internal project then uses the returned XTS token with XTS MarketData APIs.

## 3. Generate App Access

Only the QuantTrade super admin can generate internal app credentials.

1. Open QuantTrade web app.
2. Log in as the super admin.
3. Open `Admin Apps` from the sidebar.
4. Enter the internal project/app name, for example `Risk Engine` or `Backtest Service`.
5. Click `Generate`.
6. Copy and securely store:

```text
APP_KEY
APP_PASSWORD
```

The app password is shown only once. If lost, rotate the credential from `Admin Apps`.

## 4. Get XTS MarketData Token

Endpoint:

```text
POST https://quantapi.phoneme.in/api/internal/xts/marketdata/token
```

Authentication:

```text
HTTP Basic Auth
username = APP_KEY
password = APP_PASSWORD
```

Curl example:

```bash
curl -X POST "https://quantapi.phoneme.in/api/internal/xts/marketdata/token" \
  -u "qt_key_xxxxxxxxxxxxxxxxx:qt_app_xxxxxxxxxxxxxxxxx"
```

Success response:

```json
{
  "ok": true,
  "token": "XTS_MARKETDATA_TOKEN",
  "tokenType": "XTS_MARKETDATA",
  "expiresInSeconds": 1200,
  "issuedTo": "qt_key_xxxxxxxxxxxxxxxxx"
}
```

Use `token` as the XTS MarketData authorization token.

## 5. Token Handling Rules

- Cache the token in the internal app.
- Do not request a token before every quote call.
- Refresh only when `expiresInSeconds` is low, for example below 120 seconds.
- If an XTS API call returns unauthorized/forbidden, request a fresh token once and retry.
- Store `APP_PASSWORD` only in a secret manager or protected environment variable.

## 6. Use Token With XTS MarketData APIs

Base URL:

```text
https://ttblaze.iifl.com/apimarketdata
```

Header:

```text
Authorization: XTS_MARKETDATA_TOKEN
Content-Type: application/json
```

### 6.1 Quote API

Use this when the internal project already knows `exchangeSegment` and `exchangeInstrumentID`.

Endpoint:

```text
POST https://ttblaze.iifl.com/apimarketdata/instruments/quotes
```

Example:

```bash
curl -X POST "https://ttblaze.iifl.com/apimarketdata/instruments/quotes" \
  -H "Authorization: XTS_MARKETDATA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instruments": [
      {
        "exchangeSegment": 1,
        "exchangeInstrumentID": 2885
      }
    ],
    "xtsMessageCode": 1502,
    "publishFormat": "JSON"
  }'
```

Typical use:

- Live LTP
- Previous close
- Market touchline data
- Batch quotes for multiple instruments

### 6.2 Symbol Lookup API

Use this when the project has a symbol and needs the exchange instrument ID.

Endpoint:

```text
GET https://ttblaze.iifl.com/apimarketdata/instruments/instrument/symbol
```

Example:

```bash
curl "https://ttblaze.iifl.com/apimarketdata/instruments/instrument/symbol?exchangeSegment=1&symbol=RELIANCE&series=EQ" \
  -H "Authorization: XTS_MARKETDATA_TOKEN"
```

Common segment values:

```text
1  = NSECM
2  = NSEFO
3  = NSECD
5  = MCXFO
11 = BSECM
12 = BSEFO
13 = CDEFO
```

### 6.3 Instrument Master API

Use this for building/searching a local instrument database.

Endpoint:

```text
POST https://ttblaze.iifl.com/apimarketdata/instruments/master
```

Example:

```bash
curl -X POST "https://ttblaze.iifl.com/apimarketdata/instruments/master" \
  -H "Authorization: XTS_MARKETDATA_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "exchangeSegmentList": ["NSECM"]
  }'
```

Recommendation:

- Download master data once per day or on schedule.
- Cache locally in the internal project.
- Do not call master API repeatedly for every user request.

## 7. Alternative: Use QuantTrade Proxy APIs

If the internal project only needs simple market data, prefer QuantTrade proxy APIs instead of raw XTS calls.

These APIs keep XTS token handling fully inside QuantTrade:

```text
POST https://quantapi.phoneme.in/api/xts/marketdata/symbol
POST https://quantapi.phoneme.in/api/xts/marketdata/quote
GET  https://quantapi.phoneme.in/api/xts/search?q=RELIANCE&exchange_segment=1
```

Use raw XTS token access only when the internal project truly needs direct XTS MarketData API calls.

## 8. Manage App Credentials

From `Admin Apps`, the super admin can:

- Generate a new app key/password.
- Rotate an app password.
- Disable an app.
- Re-enable an app.
- See last-used time.

If a password is exposed, rotate immediately.

## 9. Security Rules

- Do not share screenshots containing `APP_PASSWORD`.
- Do not send app passwords over email or group chat.
- Use a secret manager or protected environment variables.
- Keep app credentials for server-to-server use only.
- Do not put `APP_KEY`, `APP_PASSWORD`, or XTS token in browser/frontend code.
- Disable unused app credentials immediately.

## 10. Troubleshooting

QuantTrade token endpoint errors:

```text
404 Not found
```

`ENABLE_INTERNAL_XTS_TOKEN_API=true` is not enabled on QuantTrade API server.

```text
401 Invalid internal app credentials
```

APP_KEY/APP_PASSWORD is wrong, or the app is disabled.

```text
403 Internal app scope is not allowed
```

The app credential does not have `xts:marketdata:token` scope.

```text
429 Internal XTS token rate limit exceeded
```

The app is requesting XTS tokens too frequently. Cache the token and retry later.

```text
502
```

QuantTrade could not obtain an XTS MarketData token. Check XTS server credentials or XTS service availability.

## 11. Example End-to-End Flow

```bash
# 1. Get XTS token from QuantTrade
TOKEN=$(curl -s -X POST "https://quantapi.phoneme.in/api/internal/xts/marketdata/token" \
  -u "qt_key_xxxxxxxxxxxxxxxxx:qt_app_xxxxxxxxxxxxxxxxx" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['token'])")

# 2. Use token to fetch quote from XTS
curl -X POST "https://ttblaze.iifl.com/apimarketdata/instruments/quotes" \
  -H "Authorization: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "instruments": [
      {"exchangeSegment": 1, "exchangeInstrumentID": 2885}
    ],
    "xtsMessageCode": 1502,
    "publishFormat": "JSON"
  }'
```
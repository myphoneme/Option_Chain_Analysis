"""Unit tests for the internal-token flow and direct XTS adapter (mocked HTTP).

A live token can't be issued until the gateway enables the internal token API,
so these tests exercise the auth + parsing logic against mocked responses shaped
like the real XTS payloads.
"""
from __future__ import annotations

import json

import pytest

from app.feed.base import Instrument
from app.feed.token_provider import InternalTokenProvider, TokenError
from app.feed.xts_direct import XTSDirectAdapter, _to_instrument_direct


class FakeResp:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)

    def json(self):
        return self._payload


class FakeSession:
    """Records calls and returns queued responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def post(self, url, auth=None, timeout=None, **kw):
        self.calls.append(("POST", url, auth, kw))
        return self._responses.pop(0)

    def request(self, method, url, params=None, json=None, headers=None, timeout=None):
        self.calls.append((method, url, params, json, headers))
        return self._responses.pop(0)


# ---- token provider --------------------------------------------------------

def test_token_404_reports_feature_flag():
    sess = FakeSession([FakeResp(404, {"detail": "Not found"})])
    tp = InternalTokenProvider("qt_key_x", "qt_app_y", session=sess, cache_path=None)
    with pytest.raises(TokenError) as e:
        tp.get_token()
    assert "ENABLE_INTERNAL_XTS_TOKEN_API" in str(e.value)


def test_token_401_reports_bad_credentials():
    sess = FakeSession([FakeResp(401, {"detail": "bad"})])
    tp = InternalTokenProvider("k", "p", session=sess, cache_path=None)
    with pytest.raises(TokenError) as e:
        tp.get_token()
    assert "Invalid internal app credentials" in str(e.value)


def test_token_success_and_caching():
    sess = FakeSession([
        FakeResp(200, {"ok": True, "token": "XTSTOK123", "expiresInSeconds": 1200}),
    ])
    tp = InternalTokenProvider("k", "p", session=sess, cache_path=None)
    assert tp.get_token() == "XTSTOK123"
    # cached — no second HTTP call
    assert tp.get_token() == "XTSTOK123"
    assert len(sess.calls) == 1
    # basic-auth was used
    assert sess.calls[0][2] == ("k", "p")


# ---- direct adapter --------------------------------------------------------

_TOUCHLINE = {
    "ExchangeInstrumentID": 61492, "ExchangeSegment": 2,
    "LastTradedPrice": 125.35, "Close": 119.6, "TotalTradedQuantity": 96720,
    "BidInfo": {"Price": 125.6}, "AskInfo": {"Price": 126.35},
}
_OI = {"ExchangeInstrumentID": 61492, "OpenInterest": 169260,
       "UnderlyingTotalOpenInterest": 757154175}


def _adapter_with(responses):
    tp = InternalTokenProvider("k", "p", cache_path=None, session=FakeSession([
        FakeResp(200, {"ok": True, "token": "T", "expiresInSeconds": 1200})
    ]))
    return XTSDirectAdapter(token_provider=tp, session=FakeSession(responses))


def test_direct_batch_quotes_returns_real_oi():
    ad = _adapter_with([
        FakeResp(200, {"result": {"listQuotes": [json.dumps(_TOUCHLINE)]}}),  # 1501
        FakeResp(200, {"result": {"listQuotes": [json.dumps(_OI)]}}),          # 1510
    ])
    ins = [Instrument(2, 61492, "NIFTY 25AUG2026 PE 23400", "NIFTY", "25AUG2026", "PE", 23400, "OPTIDX")]
    out = ad.fetch_quotes_for(ins)
    tl, oi = out[61492]
    assert tl.ltp == 125.35 and tl.prev_close == 119.6 and tl.volume == 96720
    assert oi.oi == 169260  # <-- OI now available in direct mode
    assert ad.supports_oi is True


def test_invalid_token_400_triggers_refresh_and_retry():
    # Reproduces the live e-session-0007 'Invalid Token' (HTTP 400): the adapter
    # must refresh the token and retry once, then succeed.
    tp_sess = FakeSession([
        FakeResp(200, {"ok": True, "token": "TOK1", "expiresInSeconds": 1200}),  # initial
        FakeResp(200, {"ok": True, "token": "TOK2", "expiresInSeconds": 1200}),  # forced refresh
    ])
    tp = InternalTokenProvider("k", "p", session=tp_sess, cache_path=None)
    xts_sess = FakeSession([
        FakeResp(400, {"type": "error", "code": "e-session-0007", "description": "Invalid Token"}),
        FakeResp(200, {"result": {"listQuotes": [json.dumps(_TOUCHLINE)]}}),  # retry OK
    ])
    ad = XTSDirectAdapter(token_provider=tp, session=xts_sess)
    ins = [Instrument(2, 61492, "NIFTY 25AUG2026 PE 23400", "NIFTY", "25AUG2026", "PE", 23400, "OPTIDX")]
    out = ad.fetch_touchline_for(ins)
    assert out[61492][0].ltp == 125.35        # succeeded after refresh
    assert len(tp_sess.calls) == 2            # token minted twice (initial + forced)


def test_direct_instrument_parsing_capitalised_keys():
    ins = _to_instrument_direct({
        "ExchangeSegment": 2, "ExchangeInstrumentID": 61492,
        "DisplayName": "NIFTY 25AUG2026 PE 23400", "Series": "OPTIDX",
    })
    assert ins.underlying == "NIFTY" and ins.option_type == "PE" and ins.strike == 23400.0

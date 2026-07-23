"""Unit-test the XTS payload parsers against REAL gateway responses.

These JSON payloads were captured live from quantapi.phoneme.in during the
13-Jul-2026 audit (NIFTY 25AUG2026 PE 23400, instrument 61492). Testing the
parser offline means vendor-schema regressions fail in CI, not at 9:16 AM.
"""
from __future__ import annotations

from app.feed.xts import XTSAdapter

_REAL_TOUCHLINE = {
    "MessageCode": 1501, "ExchangeSegment": 2, "ExchangeInstrumentID": 61492,
    "LastTradedPrice": 125.35, "LastTradedQunatity": 65,
    "TotalBuyQuantity": 20865, "TotalSellQuantity": 16835,
    "TotalTradedQuantity": 96720, "AverageTradedPrice": 148.3,
    "PercentChange": 4.8076, "Open": 185.6, "High": 185.6, "Low": 125, "Close": 119.6,
    "AskInfo": {"Size": 195, "Price": 126.35, "TotalOrders": 2},
    "BidInfo": {"Size": 325, "Price": 125.6, "TotalOrders": 1},
}

_REAL_OI = {
    "MessageCode": 1510, "ExchangeSegment": 2, "ExchangeInstrumentID": 61492,
    "OpenInterest": 169260, "UnderlyingIDIndexName": "NIFTY 50",
    "UnderlyingTotalOpenInterest": 757154175,
}


def test_parse_touchline_real_payload():
    q = XTSAdapter._parse_touchline(2, 61492, _REAL_TOUCHLINE)
    assert q.ltp == 125.35
    assert q.bid == 125.6
    assert q.ask == 126.35
    assert q.volume == 96720
    assert q.prev_close == 119.6
    # premium change derivable: LTP - prev_close
    assert round(q.ltp - q.prev_close, 2) == 5.75


def test_parse_oi_real_payload():
    q = XTSAdapter._parse_oi(2, 61492, _REAL_OI)
    assert q.oi == 169260
    assert q.underlying_total_oi == 757154175


# New simplified gateway format (captured 14-Jul-2026): result carries ltp/close
# only — no OI/volume/depth.
_NEW_SIMPLE = {"ltp": 167.15, "close": 130.1, "exchangeInstrumentID": 61492,
               "source": "xts", "resolved": True}


def test_parse_touchline_new_simple_format():
    q = XTSAdapter._parse_touchline(2, 61492, _NEW_SIMPLE)
    assert q.ltp == 167.15
    assert q.prev_close == 130.1
    # premium change still derivable
    assert round(q.ltp - q.prev_close, 2) == 37.05
    # OI/volume genuinely absent in this format
    assert q.volume == 0


def test_new_simple_format_has_no_oi():
    assert XTSAdapter.quote_has_oi(_NEW_SIMPLE) is False
    assert XTSAdapter.quote_has_oi(_REAL_OI) is True


def test_instrument_name_parsing():
    ins = XTSAdapter._to_instrument({
        "exchangeSegment": 2, "exchangeInstrumentID": 61492,
        "name": "NIFTY 25AUG2026 PE 23400", "series": "OPTIDX",
    })
    assert ins.underlying == "NIFTY"
    assert ins.expiry == "25AUG2026"
    assert ins.option_type == "PE"
    assert ins.strike == 23400.0

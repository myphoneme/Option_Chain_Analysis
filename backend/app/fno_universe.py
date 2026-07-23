"""NSE / BSE F&O underlying universe for the script selector.

This is the *underlying list* (not live data) — the set of symbols that have
options. It is bundled so the dropdown works without hammering the gateway.
Refresh periodically from the official NSE F&O securities list / instrument
master; the live quote/OI still comes from the gateway per selection.

`segment`: XTS exchange segment for the OPTIONS of this underlying
           (2 = NSEFO, 12 = BSEFO).
`kind`:    "index" or "stock" (indices resolve spot differently).
`strike`:  typical strike interval (engine still infers from live strikes).
"""
from __future__ import annotations

from typing import Dict, List

INDICES: List[Dict] = [
    {"symbol": "NIFTY", "label": "NIFTY 50", "segment": 2, "kind": "index", "strike": 50},
    {"symbol": "BANKNIFTY", "label": "BANK NIFTY", "segment": 2, "kind": "index", "strike": 100},
    {"symbol": "FINNIFTY", "label": "FIN NIFTY", "segment": 2, "kind": "index", "strike": 50},
    {"symbol": "MIDCPNIFTY", "label": "MIDCAP NIFTY", "segment": 2, "kind": "index", "strike": 25},
    {"symbol": "NIFTYNXT50", "label": "NIFTY NEXT 50", "segment": 2, "kind": "index", "strike": 100},
    {"symbol": "SENSEX", "label": "BSE SENSEX", "segment": 12, "kind": "index", "strike": 100},
    {"symbol": "BANKEX", "label": "BSE BANKEX", "segment": 12, "kind": "index", "strike": 100},
]

# High-confidence, long-standing NSE F&O stocks (liquid large/mid caps).
# Extend/replace from the official NSE F&O list as it changes.
_STOCKS = [
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK",
    "KOTAKBANK", "ITC", "LT", "BHARTIARTL", "HINDUNILVR", "BAJFINANCE",
    "BAJAJFINSV", "MARUTI", "TATAMOTORS", "TATASTEEL", "JSWSTEEL", "HINDALCO",
    "WIPRO", "HCLTECH", "TECHM", "SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB",
    "NESTLEIND", "ASIANPAINT", "TITAN", "ULTRACEMCO", "GRASIM", "ADANIENT",
    "ADANIPORTS", "POWERGRID", "NTPC", "ONGC", "COALINDIA", "BPCL", "IOC",
    "GAIL", "TATAPOWER", "DLF", "INDUSINDBK", "BANKBARODA", "PNB", "CANBK",
    "FEDERALBNK", "IDFCFIRSTB", "AUBANK", "BAJAJ-AUTO", "HEROMOTOCO",
    "EICHERMOT", "M&M", "ASHOKLEY", "TVSMOTOR", "MOTHERSON", "BALKRISIND",
    "APOLLOTYRE", "BRITANNIA", "DABUR", "GODREJCP", "MARICO", "COLPAL",
    "TATACONSUM", "PIDILITIND", "BERGEPAINT", "SBICARD", "HDFCLIFE", "SBILIFE",
    "ICICIPRULI", "ICICIGI", "MUTHOOTFIN", "CHOLAFIN", "SHRIRAMFIN", "PFC",
    "RECLTD", "LTIM", "LTTS", "PERSISTENT", "COFORGE", "MPHASIS", "OFSS",
    "TATAELXSI", "LUPIN", "AUROPHARMA", "BIOCON", "ALKEM", "TORNTPHARM",
    "ZYDUSLIFE", "GLENMARK", "LAURUSLABS", "APOLLOHOSP", "MAXHEALTH", "VEDL",
    "NATIONALUM", "JINDALSTEL", "SAIL", "NMDC", "HINDZINC", "JSWENERGY",
    "TATACOMM", "IDEA", "INDUSTOWER", "PETRONET", "IGL", "MGL", "GUJGASLTD",
    "SIEMENS", "ABB", "HAVELLS", "VOLTAS", "BEL", "HAL", "BHEL", "CUMMINSIND",
    "POLYCAB", "DIXON", "PAGEIND", "TRENT", "NAUKRI", "ZOMATO", "PAYTM",
    "IRCTC", "CONCOR", "IEX", "MANAPPURAM", "ABCAPITAL", "ABFRL", "LICHSGFIN",
    "CANFINHOME", "DEEPAKNTR", "PIIND", "SRF", "AARTIIND", "TATACHEM", "UPL",
    "COROMANDEL", "BALRAMCHIN", "INDIGO", "INDHOTEL", "OBEROIRLTY", "GODREJPROP",
    "MFSL", "BSOFT", "ESCORTS", "BATAINDIA", "CROMPTON", "JUBLFOOD",
]

STOCKS: List[Dict] = [
    {"symbol": s, "label": s, "segment": 2, "kind": "stock", "strike": None}
    for s in sorted(set(_STOCKS))
]


def universe() -> Dict[str, List[Dict]]:
    return {"indices": INDICES, "stocks": STOCKS}


def all_underlyings() -> List[Dict]:
    return INDICES + STOCKS


def find(symbol: str) -> Dict:
    sym = symbol.upper()
    for u in all_underlyings():
        if u["symbol"] == sym:
            return u
    return {}

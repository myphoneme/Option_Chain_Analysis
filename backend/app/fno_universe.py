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


# --- live universe, derived from the exchange instrument master ------------
# The static lists above are only a FALLBACK (used when the gateway/master is
# unavailable). The master is authoritative: it always has every currently
# tradable F&O script, so additions (e.g. KEI, BSE, LICI) and delistings are
# handled automatically.

_NICE_INDEX_LABEL = {u["symbol"]: u["label"] for u in INDICES}
_INDEX_STRIKE = {u["symbol"]: u["strike"] for u in INDICES}
_SEGMENTS = (2, 12)   # NSEFO, BSEFO


def live_universe(adapter) -> Dict[str, List[Dict]]:
    """Universe from the instrument master; falls back to the static lists."""
    master = getattr(adapter, "_master", None)
    if master is None:
        return {**universe(), "source": "static"}

    indices: List[Dict] = []
    stocks: List[Dict] = []
    ok = False
    failed_segments: List[int] = []
    for seg in _SEGMENTS:
        try:
            rows = master.underlyings(seg)
        except Exception:  # noqa: BLE001 — segment unavailable (gateway down / no cache)
            failed_segments.append(seg)
            continue
        ok = True
        for u in rows:
            if u["kind"] == "index":
                u = {**u,
                     "label": _NICE_INDEX_LABEL.get(u["symbol"], u["symbol"]),
                     "strike": _INDEX_STRIKE.get(u["symbol"])}
                indices.append(u)
            else:
                stocks.append(u)
    if not ok:
        return {**universe(), "source": "static"}

    # Any segment the master couldn't serve keeps its bundled entries, so we
    # never silently lose scripts (e.g. BSE SENSEX/BANKEX when BSEFO fails).
    if failed_segments:
        have = {u["symbol"] for u in indices} | {u["symbol"] for u in stocks}
        for u in all_underlyings():
            if u.get("segment") in failed_segments and u["symbol"] not in have:
                (indices if u["kind"] == "index" else stocks).append(u)

    indices.sort(key=lambda u: u["symbol"])
    stocks.sort(key=lambda u: u["symbol"])
    source = "instrument-master" + (f" (+static for segments {failed_segments})" if failed_segments else "")
    return {"indices": indices, "stocks": stocks, "source": source}


def find_live(symbol: str, adapter=None) -> Dict:
    """Resolve a symbol's segment/kind/lot from the master, else the static list."""
    sym = symbol.upper()
    master = getattr(adapter, "_master", None) if adapter else None
    if master is not None:
        for seg in _SEGMENTS:
            try:
                for u in master.underlyings(seg):
                    if u["symbol"] == sym:
                        if u["kind"] == "index":
                            u = {**u, "strike": _INDEX_STRIKE.get(sym)}
                        return u
            except Exception:  # noqa: BLE001
                continue
    return find(sym)

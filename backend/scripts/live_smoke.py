"""Live smoke test against the XTS gateway — run during market hours.

Usage:
    XTS_ACCESS_TOKEN=<gateway token> \\
    .venv/bin/python scripts/live_smoke.py NIFTY 25AUG2026 24200 --strikes 5

It logs in, enumerates the chain for the given underlying+expiry, fetches
touchline + OI for the N strikes nearest the given spot, builds a snapshot,
runs the SOP engine, and prints the verdict. Read-only: no orders are placed.
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine import analyze
from app.feed import XTSAdapter
from app.snapshot import SnapshotStore


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("underlying")
    ap.add_argument("expiry", help="e.g. 25AUG2026 (as it appears in instrument names)")
    ap.add_argument("spot", type=float)
    ap.add_argument("--segment", type=int, default=2, help="2=NSEFO, 12=BSEFO")
    ap.add_argument("--strikes", type=int, default=5, help="strikes each side of ATM")
    ap.add_argument("--throttle", type=float, default=0.05)
    args = ap.parse_args()

    token = os.getenv("XTS_ACCESS_TOKEN")
    if not token:
        sys.exit("Set XTS_ACCESS_TOKEN (gateway access_token cookie value).")

    adapter = XTSAdapter(
        base_url=os.getenv("XTS_BASE_URL", "https://quantapi.phoneme.in"),
        access_token=token,
    )
    print(f"[1] login ...")
    adapter.login()
    print(f"[2] enumerating {args.underlying} {args.expiry} instruments ...")
    instruments = adapter.list_option_instruments(args.underlying, args.expiry, args.segment)
    print(f"    found {len(instruments)} CE/PE instruments")
    if not instruments:
        sys.exit("No instruments — check underlying/expiry spelling and segment.")

    instruments.sort(key=lambda i: abs((i.strike or 0) - args.spot))
    keep = instruments[: args.strikes * 2 * 2]  # ~N strikes each side, CE+PE
    print(f"[3] fetching quotes for {len(keep)} instruments (serial) ...")
    quotes = adapter.fetch_quotes_for(keep, throttle=args.throttle)

    store = SnapshotStore()
    snap = store.build_chain(
        underlying=args.underlying, spot=args.spot, expiry=args.expiry,
        instruments=keep, quotes=quotes,
    )
    print(f"[4] built chain with {len(snap.rows)} strikes; running SOP engine ...\n")
    v = analyze(snap)

    print(f"=== VERDICT: {v.underlying} spot {v.spot} ===")
    print(f"  ATM {int(v.atm)} | bias {v.bias.value} | confidence {v.confidence:.0%}")
    print(f"  PCR total={_f(v.pcr.total_oi_pcr)} chgOI={_f(v.pcr.change_oi_pcr)} vol={_f(v.pcr.volume_pcr)}")
    print(f"  support={v.support_strike} resistance={v.resistance_strike}")
    if v.invalidation:
        print(f"  invalidation: {v.invalidation.condition}")
    print("  strategies:")
    for s in v.strategies:
        print(f"    - [{s.trader_type}] {s.action}")
    print("\n  9-step evidence:")
    for line in v.evidence:
        print("   ", line)
    print("\nNOTE: first run of the day shows Change-in-OI = 0 (baseline captured).")
    print("Run again after a few minutes to see intraday ΔOI, or seed a day-open baseline.")


def _f(x):
    return f"{x:.2f}" if x is not None else "n/a"


if __name__ == "__main__":
    main()

"""SOP Step 8 - Strategy selection.

Maps a computed bias + conviction into the trader-type action menu from the
document's Trade-Type Decision Framework (sections 15.5 / 16.5). Deliberately
conservative: defined-risk spreads are preferred and a weak/mixed read maps to
No Trade.
"""
from __future__ import annotations

from typing import List, Optional

from .models import Bias, StrategySuggestion


def suggest(
    bias: Bias,
    confidence: float,
    atm: float,
    support: Optional[float],
    resistance: Optional[float],
    strike_interval: float,
) -> List[StrategySuggestion]:
    if bias in (Bias.NO_TRADE, Bias.NEUTRAL) or confidence < 0.35:
        return [
            StrategySuggestion(
                trader_type="All",
                action="No Trade / wait for confirmation",
                risk_note=(
                    "Premium direction, OI classification, PCR and conversion do not "
                    "yet agree. The document's Final Rule: when signals disagree, the "
                    "best trade may be no trade."
                ),
            )
        ]

    if bias == Bias.BULLISH:
        entry = f"{int(atm)} CE (ATM) or slight ITM after price sustains above ATM"
        put_short = int(support) if support else int(atm - strike_interval)
        put_hedge = int(put_short - 2 * strike_interval)
        return [
            StrategySuggestion(
                trader_type="Directional buyer",
                action=f"Prefer {entry}",
                risk_note="Avoid buying far OTM only because it is cheap; wait for sustain/breakout.",
            ),
            StrategySuggestion(
                trader_type="Option seller",
                action=f"Bull Put Spread: sell {put_short} PE, buy {put_hedge} PE hedge",
                risk_note="Defined risk only; avoid naked selling without capital and stops.",
            ),
        ]

    # BEARISH
    entry = f"{int(atm)} PE (ATM) or slight ITM after price sustains below ATM"
    call_short = int(resistance) if resistance else int(atm + strike_interval)
    call_hedge = int(call_short + 2 * strike_interval)
    return [
        StrategySuggestion(
            trader_type="Directional buyer",
            action=f"Prefer {entry}",
            risk_note="Avoid chasing after a large move; wait for pullback or breakdown confirmation.",
        ),
        StrategySuggestion(
            trader_type="Option seller",
            action=f"Bear Call Spread: sell {call_short} CE, buy {call_hedge} CE hedge",
            risk_note="Defined risk only; reversals can be sharp.",
        ),
    ]

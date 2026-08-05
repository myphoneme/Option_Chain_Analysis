"""Convert engine dataclasses to JSON-friendly dicts for the API."""
from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict

from app.engine.models import Verdict


def verdict_to_dict(v: Verdict) -> Dict[str, Any]:
    d = asdict(v)
    # Enums -> their string values.
    d["bias"] = v.bias.value
    for c in d["classifications"]:
        # asdict already stringified? Ensure enum values are plain strings.
        pass
    d["classifications"] = [
        {
            "strike": c.strike,
            "call_type": c.call_type.value,
            "put_type": c.put_type.value,
            "is_support": c.is_support,
            "is_resistance": c.is_resistance,
            "notes": c.notes,
        }
        for c in v.classifications
    ]
    if v.trade_setup is not None:
        d["trade_setup"]["reward_risk"] = v.trade_setup.reward_risk
        d["trade_setup"]["validation_failures"] = list(v.trade_setup.validation_failures)
        d["trade_setup"]["blocked"] = v.trade_setup.blocked
    d["factors"] = [
        {
            "name": f.name,
            "weight": f.weight,
            "score": round(f.score, 3),
            "available": f.available,
            "note": f.note,
            "contribution": round(f.contribution, 4),
        }
        for f in v.factors
    ]
    return d

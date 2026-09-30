"""Source tiering for SignalScore's Source Weight component (roadmap V2
§14). Loads `source_registry.json` (project root, like watchlist.json).

Deliberately NOT a "which newspaper is trustworthy" ranking — see the
roadmap's own caveat (§14): tier/weight exist only to make Signal
quality/confidence measurable, never to grade a paper's honesty. Every
one of the 23 sources currently defaults to tier A / weight 1.0 (the
user's explicit choice when this was introduced: default neutral,
adjust later from observed results rather than an AI agent guessing
"which outlet is more reputable" on someone's behalf).

A source missing from the file (a newly-added crawler, or a stale file)
defaults to tier A / weight 1.0 too — a silent typo in the registry must
never zero out or crash on a source's contribution to a signal.
"""

import json
from pathlib import Path
from typing import Dict, Optional

DEFAULT_TIER = "A"
DEFAULT_WEIGHT = 1.0


def load_source_registry(path: Optional[Path]) -> Dict[str, dict]:
    """{"VnExpress": {"tier": "A", "weight": 1.0}, ...}. Missing/unreadable
    file yields an empty registry — every lookup then falls back to the
    default via `weight_for`/`tier_for` rather than raising."""
    if not path or not Path(path).exists():
        return {}
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def weight_for(source: str, registry: Dict[str, dict]) -> float:
    entry = registry.get(source) or {}
    weight = entry.get("weight", DEFAULT_WEIGHT)
    return float(weight) if isinstance(weight, (int, float)) else DEFAULT_WEIGHT


def tier_for(source: str, registry: Dict[str, dict]) -> str:
    entry = registry.get(source) or {}
    tier = entry.get("tier", DEFAULT_TIER)
    return tier if isinstance(tier, str) and tier else DEFAULT_TIER

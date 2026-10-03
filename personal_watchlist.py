"""Personal Watchlist (roadmap V4 §29-34): a PRIVATE, local-only list of
entities/keywords the user personally wants to be pinged about on
Telegram — the roadmap's own example is "Vietcombank, ACB, MWG, FPT,
Lãi suất, Bất động sản, NHNN" (§30).

Deliberately NOT the same as watchlist.json (web/brands.py), which is
committed to this public repo and drives the public brands.html page
(share of voice, crisis alerts — mục 11 of TONG-QUAN-DU-AN.md). Roadmap
§35 is explicit that V4 is "the first version needing serious thought
about private data": committing a personal interest list to a public
GitHub repo would broadcast exactly what the user is watching to the
whole internet. Per the user's own choice, this file:

  - lives at PERSONAL_WATCHLIST_PATH (default: personal_watchlist.json
    at the project root), gitignored, never committed — see
    personal_watchlist.example.json for the format.
  - has NO public website page (no "MY RADAR" HTML) — Telegram only.
  - is entirely optional: a missing file just disables the feature,
    the same way a missing .env disables Telegram itself.

Reuses web.brands.Brand/BrandIndex for the actual word-boundary
matching (short ALL-CAPS aliases like "MWG" match case-sensitively so
they don't fire on ordinary lowercase text) instead of building a
second matching engine for what is the same underlying problem
("does this title mention entity X").
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set

from models import NewsItem
from web.brands import Brand, BrandIndex


@dataclass
class PersonalWatchlistMatch:
    entity: str
    new_article_count: int
    new_source_count: int


def load_personal_watchlist(path: Optional[Path], raw_json: Optional[str] = None) -> Optional[BrandIndex]:
    """Reads the personal watchlist from `raw_json` when given (the
    PERSONAL_WATCHLIST_JSON environment variable — how it reaches GitHub
    Actions, where the gitignored file does not exist, via a repository
    Secret), otherwise from the local file at `path`. A non-empty
    `raw_json` wins and is never silently replaced by the file: invalid
    JSON there disables the feature rather than quietly using a stale
    file. Returns None (feature
    disabled) when the file is missing, unreadable, or lists no
    entities — deliberately the opposite default from
    web.brands.load_watchlist(), whose empty watchlist means "track
    every known brand". A personal watchlist starts empty on purpose:
    there is no built-in dictionary of "things you personally care
    about" to fall back to, so nothing is watched until the user
    explicitly lists something in their own private file."""
    try:
        if raw_json and raw_json.strip():
            data = json.loads(raw_json)
        elif path and Path(path).exists():
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        else:
            return None
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None

    entities = [n for n in (data.get("entities") or []) if isinstance(n, str)]
    if not entities:
        return None

    brands: Dict[str, Brand] = {name: Brand(name, "custom", (name,)) for name in entities}
    for name, extra in (data.get("extra_aliases") or {}).items():
        base = brands.get(name)
        aliases = (base.aliases if base else (name,)) + tuple(a for a in extra if isinstance(a, str))
        brands[name] = Brand(name, "custom", aliases)

    return BrandIndex(brands.values())


def match_new_articles(index: BrandIndex, new_articles: List[NewsItem]) -> List[PersonalWatchlistMatch]:
    """Roadmap V4 §31 pipeline (title -> entity extraction -> watchlist
    matching), scoped to THIS cycle's newly-inserted articles only —
    "new_article_count"/"new_source_count" per §32/§34's own dashboard
    example ("+5 new articles, +2 new sources"). Order is insertion
    order of first match, not alphabetical, so the most-recently-
    matched entity from a caller passing newest-first articles reads
    naturally first."""
    counts: Dict[str, int] = {}
    sources: Dict[str, Set[str]] = {}
    for item in new_articles:
        for entity in index.detect(item.title):
            counts[entity] = counts.get(entity, 0) + 1
            sources.setdefault(entity, set()).add(item.source)
    return [
        PersonalWatchlistMatch(entity=e, new_article_count=counts[e], new_source_count=len(sources[e]))
        for e in counts
    ]

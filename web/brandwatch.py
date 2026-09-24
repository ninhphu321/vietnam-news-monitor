"""Brand monitoring: share of voice, tone breakdown and crisis escalation.

Built on web/brands.py (who is mentioned) and web/sentiment.py (how the
headline reads). Everything is computed from crawled headlines — no AI,
no outside data — and every number can be traced back to headlines.

Definitions
-----------
mention          a headline whose text contains one of a brand's aliases
share of voice   a brand's mentions / all mentions of the tracked brands in
                 the same period (tracked = own + competitors when a
                 watchlist is configured, otherwise every known brand)
crisis alert     within the last `window_minutes`, strong/critical-negative
                 headlines about one brand come from >= `min_sources`
                 distinct outlets ("leo thang"), or from >= 2 outlets when
                 any of them uses a critical keyword ("khẩn")

Known limit: a headline naming several brands ("NHNN phạt ngân hàng X")
counts as a mention — and, if negative, as a negative mention — of each of
them. That over-attributes, which is the safe direction for an early
warning tool, but it is the first thing to check when an alert looks odd.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from web.brands import BrandIndex, Watchlist
from web.sentiment import NEGATIVE, POSITIVE, Sentiment, classify

CRISIS_MIN_SOURCES = 3
CRISIS_WINDOW_MINUTES = 60
LEVEL_ESCALATING = "leo thang"
LEVEL_URGENT = "khẩn"


def _ts(article: dict) -> Optional[datetime]:
    return article["published_at"] or article["first_seen_at"]


@dataclass
class Tagged:
    article: dict
    ts: datetime
    brands: List[str]
    sentiment: Sentiment


def tag_articles(articles: List[dict], index: BrandIndex, watch: Optional[Watchlist] = None) -> List[Tagged]:
    """Only articles that mention at least one brand are returned."""
    extra = watch.negative_extra if watch else []
    out = []
    for a in articles:
        ts = _ts(a)
        if ts is None:
            continue
        brands = index.detect(a["title"])
        if brands:
            out.append(Tagged(a, ts, brands, classify(a["title"], extra)))
    return out


def tags_by_url(tagged: List[Tagged]) -> Dict[str, Tagged]:
    return {t.article["url"]: t for t in tagged}


# ------------------------------------------------------------ share of voice
@dataclass
class BrandStat:
    brand: str
    kind: str
    role: str                      # "own" | "competitor" | "other"
    mentions: int
    sources: int
    share: float                   # 0..1 of all tracked mentions in the period
    positive: int
    negative: int
    neutral: int
    previous_mentions: int         # same-length period immediately before
    daily: List[int] = field(default_factory=list)   # last 14 days, oldest first
    recent_negative: List[dict] = field(default_factory=list)


def _tracked(index: BrandIndex, watch: Watchlist) -> List[str]:
    return watch.tracked or list(index.brands)


def share_of_voice(
    tagged: List[Tagged], index: BrandIndex, watch: Watchlist, now: datetime, days: int
) -> List[BrandStat]:
    tracked = set(_tracked(index, watch))
    start = now - timedelta(days=days)
    prev_start = start - timedelta(days=days)

    cur: Dict[str, List[Tagged]] = defaultdict(list)
    prev: Counter = Counter()
    for t in tagged:
        for b in t.brands:
            if b not in tracked:
                continue
            if start <= t.ts <= now:
                cur[b].append(t)
            elif prev_start <= t.ts < start:
                prev[b] += 1

    total = sum(len(v) for v in cur.values()) or 1
    day0 = now.replace(hour=0, minute=0, second=0, microsecond=0)
    stats = []
    for b in tracked:
        items = cur.get(b, [])
        role = "own" if b in watch.own else "competitor" if b in watch.competitors else "other"
        daily = [0] * 14
        for t in [x for x in tagged if b in x.brands]:
            offset = (day0.date() - t.ts.date()).days
            if 0 <= offset < 14:
                daily[13 - offset] += 1
        negatives = sorted((t for t in items if t.sentiment.label == NEGATIVE), key=lambda t: t.ts, reverse=True)
        stats.append(BrandStat(
            brand=b, kind=index.kind_of(b), role=role, mentions=len(items),
            sources=len({t.article["source"] for t in items}),
            share=len(items) / total,
            positive=sum(1 for t in items if t.sentiment.label == POSITIVE),
            negative=len(negatives),
            neutral=sum(1 for t in items if t.sentiment.label not in (POSITIVE, NEGATIVE)),
            previous_mentions=prev.get(b, 0), daily=daily,
            recent_negative=[
                {"title": t.article["title"], "url": t.article["url"], "source": t.article["source"],
                 "ts": t.ts, "reasons": t.sentiment.reasons}
                for t in negatives[:5]
            ],
        ))
    stats.sort(key=lambda s: (-s.mentions, s.brand))
    return stats


# ------------------------------------------------------------ crisis alerts
@dataclass
class CrisisAlert:
    brand: str
    level: str                     # "leo thang" | "khẩn"
    sources: List[str]
    articles: List[dict]
    keywords: List[str]
    window_minutes: int


def crisis_alerts(
    tagged: List[Tagged],
    now: datetime,
    watch: Optional[Watchlist] = None,
    index: Optional[BrandIndex] = None,
    window_minutes: int = CRISIS_WINDOW_MINUTES,
    min_sources: int = CRISIS_MIN_SOURCES,
) -> List[CrisisAlert]:
    start = now - timedelta(minutes=window_minutes)
    watched = set(watch.tracked) if watch and watch.tracked else None

    per_brand: Dict[str, List[Tagged]] = defaultdict(list)
    for t in tagged:
        if not (start <= t.ts <= now) or not t.sentiment.is_crisis_grade:
            continue
        for b in t.brands:
            if watched is None or b in watched:
                per_brand[b].append(t)

    alerts = []
    for brand, items in per_brand.items():
        sources = sorted({t.article["source"] for t in items})
        critical = any(t.sentiment.severity >= 3 for t in items)
        if len(sources) >= min_sources:
            level = LEVEL_URGENT if critical else LEVEL_ESCALATING
        elif critical and len(sources) >= 2:
            level = LEVEL_URGENT
        else:
            continue
        keywords = sorted({k for t in items for k in t.sentiment.reasons})
        alerts.append(CrisisAlert(
            brand=brand, level=level, sources=sources,
            articles=[{"title": t.article["title"], "url": t.article["url"], "source": t.article["source"],
                       "ts": t.ts} for t in sorted(items, key=lambda x: x.ts)],
            keywords=keywords, window_minutes=window_minutes,
        ))
    alerts.sort(key=lambda a: (0 if a.level == LEVEL_URGENT else 1, -len(a.sources), a.brand))
    return alerts

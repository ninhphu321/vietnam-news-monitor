"""Data analytics computed purely from the crawled article set — no
extra data sources, no AI. Every function takes plain article dicts
({source, title, url, published_at, first_seen_at}) and returns plain
data, so it is trivially unit-testable and the site generator only
renders the results.

Feature group "A" of the market-analysis roadmap:
  1. first_movers      — who publishes an issue first, and by how much
  2. coverage_gaps     — single-source ("exclusive") issues, and big
                         issues that major outlets have not covered
  3. collection_lag    — first_seen_at - published_at per source
  4. hourly_rhythm     — when each source publishes
  5. volume_by_topic   — daily article volume, overall and per topic
  6. reposts           — near-duplicate headlines re-posted by one source
  7. cooccurrence      — which entities/topics appear together
  8. topic_mix         — each source's topic profile

Everything except `reposts`/`hourly_rhythm` reuses the same Entity /
Topic / Issue vocabulary as web/issues.py, so the two never disagree
about what "an issue" is.
"""

import re
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from web.issues import (
    MIN_ARTICLES_THRESHOLD,
    MIN_SOURCES_THRESHOLD,
    _dedupe_overlapping,
    _entity_display,
    _extract_entities,
    _extract_topics,
    _group_by_issue,
    _issue_title,
    _passes_threshold,
)

WINDOW_DAYS = 7          # default look-back for cross-day statistics
VOLUME_DAYS = 14         # look-back for the volume-over-time chart
MAX_COLLECTION_LAG_MIN = 360   # ignore lags above 6h: those are backfills/baselines, not crawl delay
MIN_SAMPLES = 5          # don't publish a per-source statistic from fewer observations
REPOST_JACCARD = 0.8
REPOST_WINDOW = timedelta(hours=24)


def _ts(article: dict) -> Optional[datetime]:
    return article["published_at"] or article["first_seen_at"]


def _in_window(articles: List[dict], now: datetime, days: int) -> List[dict]:
    start = now - timedelta(days=days)
    out = []
    for a in articles:
        ts = _ts(a)
        if ts is not None and start <= ts <= now:
            out.append(a)
    return out


# ---------------------------------------------------------------- 1 + 2
def _day_groups(articles: List[dict], day_end: datetime) -> List[dict]:
    """Issue groups for the single calendar day ending at `day_end`
    (reuses the exact grouping + dedupe web/issues.py applies to today)."""
    groups = _group_by_issue(articles, day_end)
    groups = [g for g in groups if _passes_threshold(g, MIN_ARTICLES_THRESHOLD, MIN_SOURCES_THRESHOLD)]
    return _dedupe_overlapping(groups)


def _first_mover_of(group: dict) -> dict:
    """Earliest article per source -> who was first, and every other
    source's lag behind it in minutes."""
    firsts: Dict[str, datetime] = {}
    for s in group["samples"]:
        if s["source"] not in firsts or s["ts"] < firsts[s["source"]]:
            firsts[s["source"]] = s["ts"]
    ordered = sorted(firsts.items(), key=lambda kv: (kv[1], kv[0]))
    first_source, first_ts = ordered[0]
    lags = {src: round((ts - first_ts).total_seconds() / 60, 1) for src, ts in ordered[1:]}
    return {"first_source": first_source, "first_at": first_ts, "lags": lags, "sources": len(ordered)}


@dataclass
class FirstMoverRow:
    source: str
    first_count: int
    participated: int
    first_rate: float
    median_lag_min: Optional[float]   # median minutes behind the leader, when not first


def first_movers(articles: List[dict], now: datetime, days: int = WINDOW_DAYS) -> Tuple[List[FirstMoverRow], List[dict]]:
    """Returns (leaderboard over the last `days` days, today's multi-source
    issues with who broke each one)."""
    first_count: Counter = Counter()
    participated: Counter = Counter()
    behind: Dict[str, List[float]] = defaultdict(list)
    today_rows: List[dict] = []

    for offset in range(days):
        day = (now - timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        day_end = min(day + timedelta(days=1) - timedelta(seconds=1), now)
        day_articles = [a for a in articles if _ts(a) is not None and day <= _ts(a) <= day_end]
        for g in _day_groups(day_articles, day_end):
            if len(g["sources"]) < 2:
                continue
            fm = _first_mover_of(g)
            first_count[fm["first_source"]] += 1
            for src in [fm["first_source"], *fm["lags"]]:
                participated[src] += 1
            for src, lag in fm["lags"].items():
                behind[src].append(lag)
            if offset == 0:
                sample_titles = [s["title"] for s in g["samples"]]
                today_rows.append({
                    "title": _issue_title(g["key"], sample_titles),
                    "first_source": fm["first_source"],
                    "first_at": fm["first_at"],
                    "sources": fm["sources"],
                    "lags": sorted(fm["lags"].items(), key=lambda kv: kv[1]),
                })

    rows = []
    for src, n in participated.items():
        if n < 2:
            continue
        lags = behind.get(src)
        rows.append(FirstMoverRow(
            source=src,
            first_count=first_count.get(src, 0),
            participated=n,
            first_rate=round(first_count.get(src, 0) / n, 3),
            median_lag_min=round(statistics.median(lags), 1) if lags else None,
        ))
    rows.sort(key=lambda r: (-r.first_count, -r.first_rate, r.source))
    today_rows.sort(key=lambda r: -r["sources"])
    return rows, today_rows


def coverage_gaps(articles: List[dict], now: datetime, top_n: int = 8, majors: int = 10) -> Tuple[List[dict], List[dict]]:
    """(exclusives, gaps) for today.
    exclusives: issues carried by exactly one source (>=3 articles) —
                possibly an exclusive, possibly one outlet's own repost run.
    gaps:       issues covered by >=4 sources, listing which of the
                `majors` most active outlets have NOT covered them."""
    window = _in_window(articles, now, 1)
    volume = Counter(a["source"] for a in _in_window(articles, now, WINDOW_DAYS))
    major_sources = [s for s, _ in volume.most_common(majors)]

    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today = [a for a in window if _ts(a) >= day_start]
    groups = _day_groups(today, now)

    exclusives, gaps = [], []
    for g in groups:
        title = _issue_title(g["key"], [s["title"] for s in g["samples"]])
        if len(g["sources"]) == 1:
            exclusives.append({"title": title, "source": next(iter(g["sources"])), "articles": len(g["urls"])})
        elif len(g["sources"]) >= 4:
            missing = [s for s in major_sources if s not in g["sources"]]
            gaps.append({"title": title, "sources": len(g["sources"]), "missing": missing})
    exclusives.sort(key=lambda r: -r["articles"])
    gaps.sort(key=lambda r: (-r["sources"], len(r["missing"])))
    return exclusives[:top_n], gaps[:top_n]


# ---------------------------------------------------------------- 3
@dataclass
class LagRow:
    source: str
    median_min: float
    p90_min: float
    samples: int


def collection_lag(articles: List[dict], now: datetime, days: int = WINDOW_DAYS) -> List[LagRow]:
    per_source: Dict[str, List[float]] = defaultdict(list)
    for a in _in_window(articles, now, days):
        if a["published_at"] is None or a["first_seen_at"] is None:
            continue
        lag = (a["first_seen_at"] - a["published_at"]).total_seconds() / 60
        lag = max(lag, 0.0)   # clock skew between the site and us
        if lag <= MAX_COLLECTION_LAG_MIN:
            per_source[a["source"]].append(lag)
    rows = []
    for src, lags in per_source.items():
        if len(lags) < MIN_SAMPLES:
            continue
        lags.sort()
        p90 = lags[min(len(lags) - 1, int(len(lags) * 0.9))]
        rows.append(LagRow(src, round(statistics.median(lags), 1), round(p90, 1), len(lags)))
    rows.sort(key=lambda r: r.median_min)
    return rows


# ---------------------------------------------------------------- 4
@dataclass
class RhythmRow:
    source: str
    peak_hour: int
    night_share: float   # share of posts between 00:00 and 05:59
    samples: int


def hourly_rhythm(articles: List[dict], now: datetime, days: int = WINDOW_DAYS) -> Tuple[List[int], List[RhythmRow]]:
    overall = [0] * 24
    per_source: Dict[str, List[int]] = defaultdict(lambda: [0] * 24)
    for a in _in_window(articles, now, days):
        if a["published_at"] is None:
            continue   # first_seen_at reflects our crawl time, not the outlet's rhythm
        h = a["published_at"].hour
        overall[h] += 1
        per_source[a["source"]][h] += 1
    rows = []
    for src, hours in per_source.items():
        total = sum(hours)
        if total < MIN_SAMPLES:
            continue
        peak = max(range(24), key=lambda h: hours[h])
        rows.append(RhythmRow(src, peak, round(sum(hours[:6]) / total, 3), total))
    rows.sort(key=lambda r: (r.peak_hour, r.source))
    return overall, rows


# ---------------------------------------------------------------- 5
def volume_by_topic(articles: List[dict], now: datetime, days: int = VOLUME_DAYS, top_topics: int = 6):
    """Returns (day_labels oldest->newest, totals per day, {topic: counts per day})."""
    day_starts = [(now - timedelta(days=d)).replace(hour=0, minute=0, second=0, microsecond=0)
                  for d in range(days - 1, -1, -1)]
    index = {d.date(): i for i, d in enumerate(day_starts)}
    totals = [0] * days
    topic_days: Dict[str, List[int]] = defaultdict(lambda: [0] * days)
    for a in articles:
        ts = _ts(a)
        if ts is None or ts > now:
            continue
        i = index.get(ts.date())
        if i is None:
            continue
        totals[i] += 1
        for t in _extract_topics(a["title"]):
            topic_days[t][i] += 1
    best = sorted(topic_days.items(), key=lambda kv: -sum(kv[1]))[:top_topics]
    return [d.date() for d in day_starts], totals, dict(best)


# ---------------------------------------------------------------- 6
_WORD = re.compile(r"[^\W_]+", re.UNICODE)


def _title_tokens(title: str) -> Tuple[frozenset, frozenset]:
    """(word tokens, numeric tokens). Numbers are compared for exact
    equality, not folded into the similarity score: a daily template
    such as "Top cổ phiếu đáng chú ý đầu phiên 15/09" vs "... 16/09" is
    99% the same words but is a different post, not a repost."""
    tokens = [w.lower() for w in _WORD.findall(title)]
    return (frozenset(t for t in tokens if not t.isdigit()),
            frozenset(t for t in tokens if t.isdigit()))


def reposts(articles: List[dict], now: datetime, days: int = WINDOW_DAYS) -> Tuple[List[dict], List[dict]]:
    """Near-duplicate headlines (Jaccard >= 0.8) re-posted by the SAME
    source within 24h. Returns (per-source stats, up to 8 examples)."""
    by_source: Dict[str, List[Tuple[datetime, Tuple[frozenset, frozenset], str]]] = defaultdict(list)
    for a in _in_window(articles, now, days):
        by_source[a["source"]].append((_ts(a), _title_tokens(a["title"]), a["title"]))

    stats, examples = [], []
    for src, items in by_source.items():
        items.sort(key=lambda x: x[0])
        dupes = 0
        for i, (ts_i, (tok_i, num_i), title_i) in enumerate(items):
            if not tok_i:
                continue
            for j in range(i - 1, -1, -1):
                ts_j, (tok_j, num_j), title_j = items[j]
                if ts_i - ts_j > REPOST_WINDOW:
                    break
                if num_i == num_j and tok_j and len(tok_i & tok_j) / len(tok_i | tok_j) >= REPOST_JACCARD:
                    dupes += 1
                    if len(examples) < 8:
                        examples.append({"source": src, "first": title_j, "again": title_i})
                    break
        if len(items) >= MIN_SAMPLES:
            stats.append({"source": src, "reposts": dupes, "total": len(items),
                          "rate": round(dupes / len(items), 3)})
    stats.sort(key=lambda r: (-r["reposts"], -r["rate"], r["source"]))
    return stats, examples


# ---------------------------------------------------------------- 7
# Tokens the entity heuristic yields from ordinary place names ("TP.HCM"
# splits into "TP" + "HCM") — real, but pure noise as a co-occurrence.
_COOC_NOISE = {"vn", "tp", "hcm"}


def cooccurrence(articles: List[dict], now: datetime, days: int = WINDOW_DAYS, top_n: int = 10):
    """(top entity+topic pairs, top entity+entity pairs) over the window."""
    et: Counter = Counter()
    ee: Counter = Counter()
    display: Dict[str, str] = {}
    for a in _in_window(articles, now, days):
        entities = sorted(_extract_entities(a["title"]) - _COOC_NOISE)
        topics = sorted(_extract_topics(a["title"]))
        for e in entities:
            display.setdefault(e, _entity_display(e, [a["title"]]))
            for t in topics:
                et[(e, t)] += 1
        for i in range(len(entities)):
            for j in range(i + 1, len(entities)):
                ee[(entities[i], entities[j])] += 1
    entity_topic = [{"entity": display[e], "topic": t, "count": c}
                    for (e, t), c in et.most_common(top_n) if c >= 2]
    entity_entity = [{"a": display.get(a, a), "b": display.get(b, b), "count": c}
                     for (a, b), c in ee.most_common(top_n) if c >= 2]
    return entity_topic, entity_entity


# ---------------------------------------------------------------- 8
def topic_mix(articles: List[dict], now: datetime, days: int = WINDOW_DAYS, top_topics: int = 8):
    """(topics, {source: {topic: share of that source's articles}}, {source: n})."""
    per_source_topics: Dict[str, Counter] = defaultdict(Counter)
    per_source_total: Counter = Counter()
    overall: Counter = Counter()
    for a in _in_window(articles, now, days):
        per_source_total[a["source"]] += 1
        for t in _extract_topics(a["title"]):
            per_source_topics[a["source"]][t] += 1
            overall[t] += 1
    topics = [t for t, _ in overall.most_common(top_topics)]
    matrix = {}
    for src, total in per_source_total.items():
        if total < MIN_SAMPLES:
            continue
        matrix[src] = {t: round(per_source_topics[src][t] / total, 3) for t in topics}
    return topics, matrix, {s: per_source_total[s] for s in matrix}


# ---------------------------------------------------------------- bundle
@dataclass
class Analytics:
    first_mover_rows: List[FirstMoverRow] = field(default_factory=list)
    first_mover_today: List[dict] = field(default_factory=list)
    exclusives: List[dict] = field(default_factory=list)
    gaps: List[dict] = field(default_factory=list)
    lag_rows: List[LagRow] = field(default_factory=list)
    hourly_overall: List[int] = field(default_factory=lambda: [0] * 24)
    rhythm_rows: List[RhythmRow] = field(default_factory=list)
    volume_days: list = field(default_factory=list)
    volume_totals: List[int] = field(default_factory=list)
    volume_topics: Dict[str, List[int]] = field(default_factory=dict)
    repost_stats: List[dict] = field(default_factory=list)
    repost_examples: List[dict] = field(default_factory=list)
    entity_topic: List[dict] = field(default_factory=list)
    entity_entity: List[dict] = field(default_factory=list)
    mix_topics: List[str] = field(default_factory=list)
    mix_matrix: Dict[str, Dict[str, float]] = field(default_factory=dict)
    mix_totals: Dict[str, int] = field(default_factory=dict)


def compute_analytics(articles: List[dict], now: datetime) -> Analytics:
    if now.tzinfo is None:
        raise ValueError("compute_analytics() requires a timezone-aware `now`")
    a = Analytics()
    a.first_mover_rows, a.first_mover_today = first_movers(articles, now)
    a.exclusives, a.gaps = coverage_gaps(articles, now)
    a.lag_rows = collection_lag(articles, now)
    a.hourly_overall, a.rhythm_rows = hourly_rhythm(articles, now)
    a.volume_days, a.volume_totals, a.volume_topics = volume_by_topic(articles, now)
    a.repost_stats, a.repost_examples = reposts(articles, now)
    a.entity_topic, a.entity_entity = cooccurrence(articles, now)
    a.mix_topics, a.mix_matrix, a.mix_totals = topic_mix(articles, now)
    return a


# ---------------------------------------------------------------- data infra
def daily_stats_rows(articles: List[dict], only_days: Optional[set] = None) -> List[Tuple[str, str, str, int]]:
    """(day, kind, name, articles) rows for the `daily_stats` table, kind
    being 'source' or 'topic'. `only_days` (set of `date`) limits the work
    to a recent slice; None recomputes every day (first-run backfill)."""
    counts: Counter = Counter()
    for a in articles:
        ts = _ts(a)
        if ts is None:
            continue
        day = ts.date()
        if only_days is not None and day not in only_days:
            continue
        counts[(day.isoformat(), "source", a["source"])] += 1
        for t in _extract_topics(a["title"]):
            counts[(day.isoformat(), "topic", t)] += 1
    return [(d, k, n, c) for (d, k, n), c in sorted(counts.items())]


@dataclass
class IssueStreak:
    issue_id: str
    title: str
    days: int              # distinct days it made Top Issues
    current_streak: int    # consecutive days ending today (0 if not on today's list)
    best_rank: int
    peak_hot: float
    last_day: str


def issue_streaks(history: List[dict], today: date, top_n: int = 10) -> List[IssueStreak]:
    """Fold issue_history rows into one row per issue: how many days it
    was hot, and the consecutive-day streak ending today."""
    from datetime import date as _date

    by_issue: Dict[str, List[dict]] = defaultdict(list)
    for row in history:
        by_issue[row["issue_id"]].append(row)

    out = []
    for issue_id, rows in by_issue.items():
        days = {_date.fromisoformat(r["day"]) for r in rows}
        streak, d = 0, today
        while d in days:
            streak += 1
            d -= timedelta(days=1)
        latest = max(rows, key=lambda r: r["day"])
        out.append(IssueStreak(
            issue_id=issue_id, title=latest["title"], days=len(days), current_streak=streak,
            best_rank=min(r["rank"] for r in rows), peak_hot=max(r["hot_score"] for r in rows),
            last_day=latest["day"],
        ))
    out.sort(key=lambda s: (-s.current_streak, -s.days, -s.peak_hot))
    return out[:top_n]


def trend_from_stats(stats: List[dict], today: date, days: int = 30, top_topics: int = 6):
    """(day list, total per day, {topic: per-day counts}) straight from
    daily_stats rows — no article rescan."""
    day_list = [today - timedelta(days=d) for d in range(days - 1, -1, -1)]
    idx = {d.isoformat(): i for i, d in enumerate(day_list)}
    totals = [0] * days
    topics: Dict[str, List[int]] = defaultdict(lambda: [0] * days)
    for row in stats:
        i = idx.get(row["day"])
        if i is None:
            continue
        if row["kind"] == "source":
            totals[i] += row["articles"]
        else:
            topics[row["name"]][i] = row["articles"]
    best = dict(sorted(topics.items(), key=lambda kv: -sum(kv[1]))[:top_topics])
    return day_list, totals, best

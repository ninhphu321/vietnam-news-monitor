"""Historical Intelligence (roadmap V5 §38-45): turns data the crawl job
already persists — issue_history, signal_events, daily_stats, plus the
raw articles — into "what has been happening" views. Pure functions, no
I/O: web/generate_site.py owns rendering, web/exports.py owns the
JSON/CSV files.

Honest limits (also in TONG-QUAN-DU-AN.md mục 18):
  - issue_history only has issues that made a day's Top 5, one row per
    (day, issue) holding the latest cycle's numbers. So "issue history"
    here means "history of issues that were ever Top 5", and "total
    sources" is reported as the most sources in any single day (the
    table stores counts, not source lists, so a distinct total across
    days is not recoverable).
  - There is deliberately no ARCHIVED signal state (see web/signals.py);
    an issue that drops out simply stops appearing on later days.
  - Nothing here ranks "importance" — roadmap §40: never claim "most
    important event" without a definition.
"""

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from core.normalization import normalize_for_matching
from web.signals import ACCELERATING


# ------------------------------------------------------------ issue history
@dataclass
class IssueHistory:
    issue_id: str
    title: str
    first_detected: str            # ISO timestamp (or day) of its first appearance
    last_day: str
    days_active: int
    total_articles: int            # sum of each Top-5 day's article_count
    max_sources: int               # most distinct sources in any single day
    peak_day: str                  # day with the most articles (earliest on ties)
    peak_articles: int
    peak_velocity: Optional[float]
    best_rank: int
    peak_hot: float
    latest_status: Optional[str]


def issue_histories(rows: Sequence[dict]) -> List[IssueHistory]:
    """Fold issue_history rows into one summary per issue (roadmap §40),
    most recently active first."""
    by_issue: Dict[str, List[dict]] = defaultdict(list)
    for row in rows:
        by_issue[row["issue_id"]].append(row)

    out = []
    for issue_id, rs in by_issue.items():
        rs = sorted(rs, key=lambda r: r["day"])
        latest = rs[-1]
        peak = max(rs, key=lambda r: r["article_count"])  # first max = earliest day
        seen = [r["first_seen_at"] for r in rs if r.get("first_seen_at")]
        velocities = [r["velocity"] for r in rs if r.get("velocity") is not None]
        out.append(IssueHistory(
            issue_id=issue_id,
            title=latest["title"],
            first_detected=min(seen) if seen else rs[0]["day"],
            last_day=latest["day"],
            days_active=len({r["day"] for r in rs}),
            total_articles=sum(r["article_count"] for r in rs),
            max_sources=max(r["source_count"] for r in rs),
            peak_day=peak["day"],
            peak_articles=peak["article_count"],
            peak_velocity=max(velocities) if velocities else None,
            best_rank=min(r["rank"] for r in rs),
            peak_hot=max(r["hot_score"] for r in rs),
            latest_status=latest.get("signal_status"),
        ))
    out.sort(key=lambda h: (h.last_day, h.peak_hot), reverse=True)
    return out


def search_issues(histories: Sequence[IssueHistory], query: str) -> List[IssueHistory]:
    """Case/diacritic-composition-insensitive substring search (same
    normalization the matching code uses). Empty query returns all."""
    q = normalize_for_matching(query).strip()
    if not q:
        return list(histories)
    return [h for h in histories if q in normalize_for_matching(h.title)]


def period_issue_histories(rows: Sequence[dict], today: date, days: int) -> List[IssueHistory]:
    """issue_histories() restricted to the last `days` calendar days."""
    since = (today - timedelta(days=days - 1)).isoformat()
    return issue_histories([r for r in rows if r["day"] >= since])


# ----------------------------------------------------------- signal history
@dataclass
class SignalTimeline:
    day: str
    issue_id: str
    title: str
    steps: List[Tuple[str, str]]   # (status, occurred_at ISO), chronological


def signal_timelines(events: Sequence[dict], titles: Dict[str, str], limit: int = 30) -> List[SignalTimeline]:
    """Roadmap §39: per (day, issue) the status transitions in order, e.g.
    emerging 09:12 -> accelerating 10:15 -> peak 12:10. Newest first."""
    grouped: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for e in events:
        grouped[(e["day"], e["issue_id"])].append(e)
    out = []
    for (day, issue_id), evs in grouped.items():
        evs = sorted(evs, key=lambda e: e["occurred_at"])
        out.append(SignalTimeline(
            day=day, issue_id=issue_id, title=titles.get(issue_id, issue_id),
            steps=[(e["to_status"], e["occurred_at"]) for e in evs],
        ))
    out.sort(key=lambda t: t.steps[-1][1], reverse=True)
    return out[:limit]


# ------------------------------------------------------------- media memory
@dataclass
class TopicGrowth:
    name: str
    earlier: int
    recent: int
    delta: int
    pct: Optional[float]           # None when earlier == 0 ("new")


def fastest_growing_topics(
    stats: Sequence[dict], today: date, days: int = 30, limit: int = 8, min_total: int = 10
) -> List[TopicGrowth]:
    """Later half of the window vs. the earlier half, from daily_stats
    topic rows. Ranked by absolute increase (not ratio) and gated by
    `min_total`, so a topic going 1 -> 3 articles doesn't outrank a real
    surge — a first-cut choice, same "tune from real data" status as
    every other threshold in this project."""
    half = max(days // 2, 1)
    recent_start = today - timedelta(days=half - 1)
    earlier_start = today - timedelta(days=days - 1)
    earlier: Counter = Counter()
    recent: Counter = Counter()
    for row in stats:
        if row["kind"] != "topic":
            continue
        d = date.fromisoformat(row["day"])
        if recent_start <= d <= today:
            recent[row["name"]] += row["articles"]
        elif earlier_start <= d < recent_start:
            earlier[row["name"]] += row["articles"]
    out = []
    for name in set(recent) | set(earlier):
        e, r = earlier[name], recent[name]
        if e + r < min_total or r <= e:
            continue
        out.append(TopicGrowth(name, e, r, r - e, None if e == 0 else (r - e) / e))
    out.sort(key=lambda t: (-t.delta, t.name))
    return out[:limit]


def top_sources(stats: Sequence[dict], today: date, days: int = 30, limit: int = 8) -> List[Tuple[str, int]]:
    """Source history (roadmap §47): articles per source over `days`."""
    since = (today - timedelta(days=days - 1)).isoformat()
    counts: Counter = Counter()
    for row in stats:
        if row["kind"] == "source" and row["day"] >= since:
            counts[row["name"]] += row["articles"]
    return counts.most_common(limit)


# ------------------------------------------------- historical comparison §44
@dataclass
class PeriodMetrics:
    articles: int
    sources: int                   # distinct sources that published
    issues: int                    # distinct Top-5 issues seen in the period
    mentions: int                  # tracked-brand mentions (title-based)
    accelerations: int             # signals that turned ACCELERATING


@dataclass
class Comparison:
    label: str                     # "Hôm nay vs hôm qua", ...
    current_label: str
    previous_label: str
    current: PeriodMetrics
    previous: PeriodMetrics
    # False when the system started collecting AFTER the previous window
    # began: its numbers then reflect "we weren't running yet", not a real
    # change, so the page withholds the % delta instead of showing e.g.
    # "+39000%" (found on real data a few weeks into collection).
    previous_covered: bool = True
    collection_start: Optional[str] = None


def _ts(article: dict) -> Optional[datetime]:
    return article["published_at"] or article["first_seen_at"]


def comparison_windows(now: datetime, kind: str) -> Tuple[datetime, datetime, datetime, datetime]:
    """(cur_start, cur_end, prev_start, prev_end). The previous window is
    the same ELAPSED length starting one period earlier, so a half-done
    day/week/month is compared with the same slice of the last one
    instead of looking like a collapse. kind: "day" | "week" | "month"."""
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if kind == "day":
        cur_start, prev_start = midnight, midnight - timedelta(days=1)
    elif kind == "week":
        cur_start = midnight - timedelta(days=midnight.weekday())  # Monday
        prev_start = cur_start - timedelta(days=7)
    elif kind == "month":
        cur_start = midnight.replace(day=1)
        prev_start = (cur_start - timedelta(days=1)).replace(day=1)
    else:
        raise ValueError(f"unknown comparison kind: {kind!r}")
    prev_end = prev_start + (now - cur_start)
    prev_end = min(prev_end, cur_start - timedelta(microseconds=1))
    return cur_start, now, prev_start, prev_end


def period_metrics(
    articles: Sequence[dict], history: Sequence[dict], events: Sequence[dict],
    start: datetime, end: datetime, tagged: Optional[Sequence] = None,
) -> PeriodMetrics:
    in_window = [a for a in articles if (t := _ts(a)) is not None and start <= t <= end]
    first_day, last_day = start.date().isoformat(), end.date().isoformat()
    issue_ids = {r["issue_id"] for r in history if first_day <= r["day"] <= last_day}
    accel = 0
    for e in events:
        if e["to_status"] != ACCELERATING:
            continue
        try:
            when = datetime.fromisoformat(e["occurred_at"])
        except ValueError:
            continue
        if start <= when <= end:
            accel += 1
    mentions = sum(len(t.brands) for t in (tagged or []) if start <= t.ts <= end)
    return PeriodMetrics(
        articles=len(in_window), sources=len({a["source"] for a in in_window}),
        issues=len(issue_ids), mentions=mentions, accelerations=accel,
    )


_COMPARISONS = (
    ("day", "Hôm nay vs hôm qua", "Hôm nay", "Hôm qua"),
    ("week", "Tuần này vs tuần trước", "Tuần này", "Tuần trước"),
    ("month", "Tháng này vs tháng trước", "Tháng này", "Tháng trước"),
)


def compare_periods(
    articles: Sequence[dict], history: Sequence[dict], events: Sequence[dict],
    now: datetime, tagged: Optional[Sequence] = None,
) -> List[Comparison]:
    # first_seen_at (when WE first saw the article), not published_at: feeds
    # such as VTV carry weeks-old items, which would fake an early start.
    seen = [a["first_seen_at"] for a in articles if a.get("first_seen_at") is not None]
    started = min(seen) if seen else None
    out = []
    for kind, label, cur_label, prev_label in _COMPARISONS:
        cs, ce, ps, pe = comparison_windows(now, kind)
        out.append(Comparison(
            label=label, current_label=cur_label, previous_label=prev_label,
            current=period_metrics(articles, history, events, cs, ce, tagged),
            previous=period_metrics(articles, history, events, ps, pe, tagged),
            previous_covered=started is not None and started <= ps,
            collection_start=started.date().isoformat() if started else None,
        ))
    return out


# --------------------------------------------------------------- media gap §43
def major_sources(articles: Sequence[dict], now: datetime, n: int = 10, days: int = 7) -> List[str]:
    """The `n` most active outlets over the last `days` — same notion of
    "major" web/analytics.coverage_gaps already uses."""
    start = now - timedelta(days=days)
    volume = Counter(a["source"] for a in articles if (t := _ts(a)) is not None and start <= t <= now)
    return [s for s, _ in volume.most_common(n)]


def missing_major_sources(issue_sources: Sequence[str], majors: Sequence[str]) -> List[str]:
    """Tracked major outlets with no matching article for this issue.
    Absence of a *title match* only — never "ignored the story" (roadmap
    §43: say "no matching article detected", nothing stronger)."""
    covered = set(issue_sources)
    return [s for s in majors if s not in covered]

"""Machine-readable exports written next to the HTML pages, so the data
is reusable outside the website (Excel/Power BI, Slack/Feedly, scripts):

  issues.json — today's Top Issues with all four HotScore components
  stats.json  — daily per-source / per-topic counts and issue history
  feed.xml    — RSS 2.0 of the newest articles across all sources
  history.json / signals.json / issues_history.csv — roadmap V5: per-issue
                history, the signal_events log, and a CSV of the same

Pure functions returning strings/dicts; build_site does the file I/O.
"""

import csv
import io
import json
from dataclasses import asdict
from datetime import datetime, timezone
from email.utils import format_datetime
from typing import List, Sequence
from xml.sax.saxutils import escape

from web.history import Comparison, IssueHistory
from web.issues import Issue

FEED_ITEMS = 100


def issues_json(issues: List[Issue], now: datetime) -> str:
    payload = {
        "generated_at": now.isoformat(),
        "day": now.date().isoformat(),
        "issues": [
            {
                "rank": rank,
                "id": i.issue_id,
                "title": i.issue_title,
                "hot_score": i.hot_score,
                "components": {
                    "volume": i.volume_score, "source": i.source_score,
                    "velocity": i.velocity_score, "novelty": i.novelty_score,
                },
                "article_count": i.article_count,
                "source_count": i.unique_source_count,
                "sources": i.sources,
                "first_seen_at": i.first_seen_at.isoformat(),
                "last_seen_at": i.last_seen_at.isoformat(),
                "why_hot": i.why_hot,
                # Rebuilt rather than passed straight through: all_articles
                # carries an internal-only "ts" datetime (roadmap V3 §25)
                # that isn't JSON-serializable and isn't part of this
                # export's public contract — keep it to exactly the
                # {title, url, source} shape this API has always had.
                "articles": [
                    {"title": a["title"], "url": a["url"], "source": a["source"]}
                    for a in i.all_articles
                ],
            }
            for rank, i in enumerate(issues, start=1)
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def stats_json(daily_stats: List[dict], issue_history: List[dict], now: datetime) -> str:
    daily = {}
    for row in daily_stats:
        daily.setdefault(row["day"], {"sources": {}, "topics": {}})[
            "sources" if row["kind"] == "source" else "topics"
        ][row["name"]] = row["articles"]
    payload = {
        "generated_at": now.isoformat(),
        "daily": daily,
        "issue_history": issue_history,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def feed_xml(articles: List[dict], site_url: str, now: datetime, limit: int = FEED_ITEMS) -> str:
    """RSS 2.0, newest first. Uses published_at, falling back to
    first_seen_at (always present) exactly like the rest of the site."""
    ordered = sorted(articles, key=lambda a: a["published_at"] or a["first_seen_at"], reverse=True)[:limit]
    items = []
    for a in ordered:
        ts = a["published_at"] or a["first_seen_at"]
        items.append(
            "<item>"
            f"<title>{escape(a['title'])}</title>"
            f"<link>{escape(a['url'])}</link>"
            f"<guid isPermaLink=\"true\">{escape(a['url'])}</guid>"
            f"<category>{escape(a['source'])}</category>"
            f"<pubDate>{format_datetime(ts.astimezone(timezone.utc))}</pubDate>"
            "</item>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<rss version="2.0"><channel>'
        "<title>Vietnam News Monitor</title>"
        f"<link>{escape(site_url)}</link>"
        "<description>Tin tài chính - kinh doanh tổng hợp từ nhiều báo Việt Nam</description>"
        "<language>vi</language>"
        f"<lastBuildDate>{format_datetime(now.astimezone(timezone.utc))}</lastBuildDate>"
        + "".join(items)
        + "</channel></rss>\n"
    )


def brands_json(stats7, stats30, alerts, watch, now: datetime) -> str:
    """Brand monitoring export: share of voice (7/30 days), tone counts and
    any active crisis alerts. `role` is own / competitor / other."""
    def stat(s):
        return {
            "brand": s.brand, "role": s.role, "kind": s.kind, "mentions": s.mentions,
            "sources": s.sources, "share": round(s.share, 4),
            "tone": {"positive": s.positive, "negative": s.negative, "neutral": s.neutral},
            "previous_period_mentions": s.previous_mentions, "daily_14d": s.daily,
        }

    payload = {
        "generated_at": now.isoformat(),
        "watchlist": {"own": watch.own, "competitors": watch.competitors},
        "share_of_voice_7d": [stat(s) for s in stats7 if s.mentions or s.role != "other"],
        "share_of_voice_30d": [stat(s) for s in stats30 if s.mentions or s.role != "other"],
        "crisis_alerts": [
            {
                "brand": a.brand, "level": a.level, "sources": a.sources, "keywords": a.keywords,
                "window_minutes": a.window_minutes,
                "articles": [{**x, "ts": x["ts"].isoformat()} for x in a.articles],
            }
            for a in alerts
        ],
        "note": "Tone labels are keyword-based estimates from headlines only.",
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def history_json(histories: Sequence[IssueHistory], comparisons: Sequence[Comparison], now: datetime) -> str:
    """Roadmap V5 §45 history.json: one summary per issue that ever made a
    Top 5 (web/history.py documents what that does and doesn't cover)
    plus the day/week/month comparisons."""
    payload = {
        "generated_at": now.isoformat(),
        "issues": [asdict(h) for h in histories],
        "comparisons": [asdict(c) for c in comparisons],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def signals_json(events: Sequence[dict], now: datetime) -> str:
    """Roadmap V5 §45 signals.json: the append-only signal_events log
    (every real lifecycle transition), oldest first."""
    payload = {
        "generated_at": now.isoformat(),
        "events": sorted(events, key=lambda e: e["occurred_at"]),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def issues_history_csv(histories: Sequence[IssueHistory]) -> str:
    """Roadmap V5 §45 CSV export of the same per-issue summaries."""
    fields = list(IssueHistory.__dataclass_fields__)
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for h in histories:
        writer.writerow(asdict(h))
    return buf.getvalue()

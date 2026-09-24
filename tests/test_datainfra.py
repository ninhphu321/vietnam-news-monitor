"""Tests for the data infrastructure: daily_stats, issue_history,
snapshot_data, JSON/RSS exports and the monthly archive."""

import gzip
import json
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from archive import archive_old_articles
from models import NewsItem
from scheduler import snapshot_data
from web.analytics import daily_stats_rows, issue_streaks, trend_from_stats
from web.exports import feed_xml, issues_json, stats_json
from web.issues import top_issues

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
NOW = datetime(2026, 9, 17, 18, 0, tzinfo=TZ)
T9 = datetime(2026, 9, 17, 9, 0, tzinfo=TZ)
TITLE = "Eximbank tăng vốn điều lệ lên 20.000 tỷ đồng"


def _art(source, title, when, url=None):
    return {"source": source, "title": title, "url": url or f"https://x/{source}/{title}/{when}",
            "published_at": when, "first_seen_at": when + timedelta(minutes=5)}


def _issue_articles():
    return [_art(s, TITLE, T9 + timedelta(minutes=i)) for i, s in enumerate(["CafeF", "VnExpress", "Dân Trí"])]


# --- database tables ---------------------------------------------------------
def test_replace_daily_stats_replaces_only_the_given_days(db):
    db.replace_daily_stats(["2026-09-16", "2026-09-17"], [
        ("2026-09-16", "source", "CafeF", 5), ("2026-09-17", "source", "CafeF", 9)])
    db.replace_daily_stats(["2026-09-17"], [("2026-09-17", "source", "CafeF", 2)])
    rows = {(r["day"], r["name"]): r["articles"] for r in db.get_daily_stats()}
    assert rows == {("2026-09-16", "CafeF"): 5, ("2026-09-17", "CafeF"): 2}


def test_record_issues_upserts_the_latest_values_per_day(db):
    issue = {"issue_id": "eximbank-tang-von", "title": "Eximbank · Tăng vốn", "rank": 3, "hot_score": 50.0,
             "article_count": 3, "source_count": 3}
    db.record_issues("2026-09-17", [issue], NOW)
    db.record_issues("2026-09-17", [{**issue, "rank": 1, "hot_score": 80.0}], NOW)
    rows = db.get_issue_history()
    assert len(rows) == 1 and rows[0]["rank"] == 1 and rows[0]["hot_score"] == 80.0


# --- pure helpers ------------------------------------------------------------
def test_daily_stats_rows_counts_sources_and_topics_per_day():
    arts = [_art("CafeF", "Lãi suất tăng", T9), _art("CafeF", "Lãi suất giảm", T9),
            _art("VnExpress", "Giá vàng đi ngang", T9 - timedelta(days=1))]
    rows = set(daily_stats_rows(arts))
    assert ("2026-09-17", "source", "CafeF", 2) in rows
    assert ("2026-09-17", "topic", "lãi suất", 2) in rows
    assert ("2026-09-16", "topic", "giá vàng", 1) in rows
    only_today = daily_stats_rows(arts, {date(2026, 9, 17)})
    assert all(r[0] == "2026-09-17" for r in only_today)


def test_issue_streak_counts_consecutive_days_ending_today():
    def h(day, rank=2, hot=60.0):
        return {"day": day, "issue_id": "a", "title": "A", "rank": rank, "hot_score": hot}

    history = [h("2026-09-17"), h("2026-09-16", rank=1, hot=90.0), h("2026-09-15"), h("2026-09-12")]
    st = issue_streaks(history, date(2026, 9, 17))[0]
    assert st.current_streak == 3 and st.days == 4
    assert st.best_rank == 1 and st.peak_hot == 90.0
    assert issue_streaks(history, date(2026, 9, 18))[0].current_streak == 0


def test_trend_from_stats_sums_sources_and_keeps_topics():
    stats = [{"day": "2026-09-17", "kind": "source", "name": "CafeF", "articles": 4},
             {"day": "2026-09-17", "kind": "source", "name": "VnExpress", "articles": 6},
             {"day": "2026-09-17", "kind": "topic", "name": "lãi suất", "articles": 3}]
    days, totals, topics = trend_from_stats(stats, date(2026, 9, 17), days=3)
    assert totals == [0, 0, 10] and topics["lãi suất"] == [0, 0, 3] and days[-1] == date(2026, 9, 17)


# --- snapshot_data (what the crawl job persists) -----------------------------
def test_snapshot_data_persists_issue_history_and_daily_stats(db):
    for a in _issue_articles():
        db.insert_if_new(NewsItem(a["source"], a["title"], a["url"], a["published_at"]))
    snapshot_data(db, NOW)
    assert db.get_issue_history() and db.get_daily_stats()
    assert not db.daily_stats_is_empty()


def test_snapshot_data_never_raises(db, monkeypatch):
    def boom():
        raise RuntimeError("boom")

    monkeypatch.setattr(db, "get_all_articles", boom)
    snapshot_data(db, NOW)  # secondary, best-effort step: must swallow


# --- exports -----------------------------------------------------------------
def test_issues_json_exposes_all_four_components():
    issues = top_issues(_issue_articles(), NOW)
    data = json.loads(issues_json(issues, NOW))
    assert data["issues"] and set(data["issues"][0]["components"]) == {"volume", "source", "velocity", "novelty"}
    assert data["issues"][0]["rank"] == 1


def test_stats_json_groups_by_day_and_kind():
    stats = [{"day": "2026-09-17", "kind": "source", "name": "CafeF", "articles": 4},
             {"day": "2026-09-17", "kind": "topic", "name": "lãi suất", "articles": 3}]
    data = json.loads(stats_json(stats, [], NOW))
    assert data["daily"]["2026-09-17"] == {"sources": {"CafeF": 4}, "topics": {"lãi suất": 3}}


def test_feed_xml_is_valid_rss_newest_first_and_escaped():
    arts = [_art("CafeF", "Cũ & <b>", T9 - timedelta(hours=3)), _art("VnExpress", "Mới", T9)]
    root = ET.fromstring(feed_xml(arts, "https://site/", NOW))
    titles = [i.findtext("title") for i in root.iter("item")]
    assert titles == ["Mới", "Cũ & <b>"]
    assert feed_xml(arts, "https://site/", NOW, limit=1).count("<item>") == 1


# --- monthly archive -----------------------------------------------------------
def _seed_old_and_new(db):
    db.insert_if_new(NewsItem("CafeF", "Bài rất cũ", "https://x/old", datetime(2026, 5, 3, 10, 0, tzinfo=TZ)))
    db.insert_if_new(NewsItem("CafeF", "Bài cũ khác", "https://x/old2", datetime(2026, 5, 20, 10, 0, tzinfo=TZ)))
    db.insert_if_new(NewsItem("CafeF", "Bài mới", "https://x/new", datetime(2026, 9, 16, 10, 0, tzinfo=TZ)))


def test_archive_exports_old_rows_by_month_and_keeps_them_by_default(db, tmp_path):
    _seed_old_and_new(db)
    written = archive_old_articles(db.db_path, tmp_path / "arc", 90, "Asia/Ho_Chi_Minh", now=NOW)
    assert written == {"2026-05": 2}
    with gzip.open(tmp_path / "arc" / "news-2026-05.jsonl.gz", "rt", encoding="utf-8") as fh:
        assert {json.loads(line)["url"] for line in fh} == {"https://x/old", "https://x/old2"}
    assert db.count_all() == 3


def test_archive_delete_removes_only_old_rows_and_rerun_keeps_file(db, tmp_path):
    _seed_old_and_new(db)
    archive_old_articles(db.db_path, tmp_path / "arc", 90, "Asia/Ho_Chi_Minh", delete=True, now=NOW)
    assert db.count_all() == 1
    assert archive_old_articles(db.db_path, tmp_path / "arc", 90, "Asia/Ho_Chi_Minh", delete=True, now=NOW) == {}
    with gzip.open(tmp_path / "arc" / "news-2026-05.jsonl.gz", "rt", encoding="utf-8") as fh:
        assert len(fh.readlines()) == 2

"""Tests for web/history.py — Historical Intelligence (roadmap V5)."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import csv
import io
import json

from web.exports import history_json, issues_history_csv, signals_json
from web.history import (
    compare_periods,
    comparison_windows,
    fastest_growing_topics,
    issue_histories,
    major_sources,
    missing_major_sources,
    period_issue_histories,
    search_issues,
    signal_timelines,
    top_sources,
)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
NOW = datetime(2026, 9, 17, 15, 0, tzinfo=TZ)  # a Thursday


def _row(day, issue_id="eximbank-tang-von", title="Eximbank · Tăng vốn", rank=1, hot=80.0,
         articles=5, sources=3, velocity=1.5, status="peak", first="2026-09-15T09:12:00+07:00"):
    return {"day": day, "issue_id": issue_id, "title": title, "rank": rank, "hot_score": hot,
            "article_count": articles, "source_count": sources, "first_seen_at": first,
            "last_seen_at": first, "velocity": velocity, "signal_status": status}


# --- issue history (§40) ------------------------------------------------------
def test_issue_histories_folds_days_into_one_summary():
    rows = [
        _row("2026-09-15", articles=4, sources=2, velocity=1.0, rank=3, hot=60.0),
        _row("2026-09-16", articles=9, sources=5, velocity=2.5, rank=1, hot=90.0, status="accelerating"),
        _row("2026-09-17", articles=2, sources=2, velocity=0.5, rank=2, hot=70.0, status="cooling"),
    ]
    [h] = issue_histories(rows)
    assert h.days_active == 3
    assert h.total_articles == 15
    assert h.max_sources == 5
    assert (h.peak_day, h.peak_articles) == ("2026-09-16", 9)
    assert h.peak_velocity == 2.5
    assert h.best_rank == 1 and h.peak_hot == 90.0
    assert h.latest_status == "cooling" and h.last_day == "2026-09-17"
    assert h.first_detected == "2026-09-15T09:12:00+07:00"


def test_peak_day_prefers_the_earliest_on_ties():
    rows = [_row("2026-09-15", articles=6), _row("2026-09-16", articles=6)]
    assert issue_histories(rows)[0].peak_day == "2026-09-15"


def test_rows_from_before_velocity_existed_do_not_crash():
    rows = [_row("2026-09-15", velocity=None, status=None, first=None)]
    [h] = issue_histories(rows)
    assert h.peak_velocity is None and h.latest_status is None
    assert h.first_detected == "2026-09-15"  # falls back to the day


def test_issue_histories_most_recently_active_first():
    rows = [_row("2026-09-10", issue_id="a", title="A"), _row("2026-09-16", issue_id="b", title="B")]
    assert [h.issue_id for h in issue_histories(rows)] == ["b", "a"]


def test_search_ignores_case_and_matches_substrings():
    hs = issue_histories([
        _row("2026-09-16", issue_id="a", title="Eximbank · Nhân sự lãnh đạo"),
        _row("2026-09-16", issue_id="b", title="Fed · Lãi suất"),
    ])
    assert [h.issue_id for h in search_issues(hs, "EXIMBANK")] == ["a"]
    assert [h.issue_id for h in search_issues(hs, "lãi suất")] == ["b"]
    assert search_issues(hs, "không có") == []


def test_search_treats_decomposed_unicode_like_composed():
    hs = issue_histories([_row("2026-09-16", title="Xung đột · Trung Đông")])
    decomposed = "xung đột"  # "ộ" as ô + combining dot below
    assert len(search_issues(hs, decomposed)) == 1


def test_empty_query_returns_everything():
    hs = issue_histories([_row("2026-09-16")])
    assert search_issues(hs, "  ") == hs


def test_period_issue_histories_only_counts_days_inside_the_window():
    rows = [_row("2026-08-01", articles=50), _row("2026-09-16", articles=3)]
    [h] = period_issue_histories(rows, date(2026, 9, 17), days=30)
    assert h.total_articles == 3 and h.days_active == 1


# --- signal history (§39) -----------------------------------------------------
def _event(day, issue_id, to_status, at):
    return {"day": day, "issue_id": issue_id, "from_status": None, "to_status": to_status,
            "velocity": 1.0, "article_count": 3, "source_count": 2, "occurred_at": at}


def test_signal_timeline_orders_steps_chronologically():
    events = [
        _event("2026-09-17", "x", "peak", "2026-09-17T12:10:00+07:00"),
        _event("2026-09-17", "x", "emerging", "2026-09-17T09:12:00+07:00"),
        _event("2026-09-17", "x", "accelerating", "2026-09-17T10:15:00+07:00"),
    ]
    [t] = signal_timelines(events, {"x": "Eximbank · Tăng vốn"})
    assert [s for s, _ in t.steps] == ["emerging", "accelerating", "peak"]
    assert t.title == "Eximbank · Tăng vốn"


def test_signal_timeline_separates_days_and_falls_back_to_the_id():
    events = [_event("2026-09-16", "x", "emerging", "2026-09-16T09:00:00+07:00"),
              _event("2026-09-17", "x", "emerging", "2026-09-17T09:00:00+07:00")]
    timelines = signal_timelines(events, {})
    assert [t.day for t in timelines] == ["2026-09-17", "2026-09-16"]  # newest first
    assert timelines[0].title == "x"


# --- media memory (§41) -------------------------------------------------------
def _stat(day, kind, name, n):
    return {"day": day, "kind": kind, "name": name, "articles": n}


def test_fastest_growing_topics_ranks_by_absolute_increase():
    today = date(2026, 9, 30)
    stats = [
        _stat("2026-09-05", "topic", "lãi suất", 4), _stat("2026-09-28", "topic", "lãi suất", 20),
        _stat("2026-09-05", "topic", "vàng", 5), _stat("2026-09-28", "topic", "vàng", 9),
        _stat("2026-09-28", "topic", "mới nổi", 12),
    ]
    result = fastest_growing_topics(stats, today, days=30)
    assert [t.name for t in result] == ["lãi suất", "mới nổi", "vàng"]
    assert result[0].delta == 16 and result[0].pct == pytest.approx(4.0)
    assert result[1].pct is None  # earlier == 0 -> "new"


def test_fastest_growing_topics_ignores_shrinking_and_tiny_topics():
    today = date(2026, 9, 30)
    stats = [
        _stat("2026-09-05", "topic", "giảm", 30), _stat("2026-09-28", "topic", "giảm", 5),
        _stat("2026-09-05", "topic", "nhỏ", 1), _stat("2026-09-28", "topic", "nhỏ", 3),
        _stat("2026-09-28", "source", "VnExpress", 99),
    ]
    assert fastest_growing_topics(stats, today, days=30) == []


def test_top_sources_sums_the_window_only():
    today = date(2026, 9, 30)
    stats = [_stat("2026-09-29", "source", "CafeF", 10), _stat("2026-09-30", "source", "CafeF", 5),
             _stat("2026-09-30", "source", "VnExpress", 7), _stat("2026-07-01", "source", "VnExpress", 500),
             _stat("2026-09-30", "topic", "lãi suất", 99)]
    assert top_sources(stats, today, days=30) == [("CafeF", 15), ("VnExpress", 7)]


# --- historical comparison (§44) ----------------------------------------------
def test_day_window_compares_the_same_elapsed_hours():
    cs, ce, ps, pe = comparison_windows(NOW, "day")
    assert cs == datetime(2026, 9, 17, 0, 0, tzinfo=TZ) and ce == NOW
    assert ps == datetime(2026, 9, 16, 0, 0, tzinfo=TZ)
    assert pe == datetime(2026, 9, 16, 15, 0, tzinfo=TZ)


def test_week_window_starts_on_monday_and_matches_elapsed_time():
    cs, _, ps, pe = comparison_windows(NOW, "week")
    assert cs.date() == date(2026, 9, 14) and ps.date() == date(2026, 9, 7)
    assert pe == ps + (NOW - cs)


def test_month_window_never_spills_into_the_current_month():
    now = datetime(2026, 3, 31, 12, 0, tzinfo=TZ)  # February only has 28 days
    cs, _, ps, pe = comparison_windows(now, "month")
    assert ps.date() == date(2026, 2, 1)
    assert pe < cs


def test_unknown_window_kind_is_rejected():
    with pytest.raises(ValueError):
        comparison_windows(NOW, "year")


def _art(source, when):
    return {"source": source, "title": "t", "url": f"u/{source}/{when}", "published_at": when, "first_seen_at": when}


def test_compare_periods_counts_each_metric_inside_its_own_window():
    articles = [
        _art("VnExpress", NOW - timedelta(hours=1)), _art("CafeF", NOW - timedelta(hours=2)),
        _art("VnExpress", NOW - timedelta(days=1, hours=1)),
        _art("CafeF", NOW - timedelta(hours=20)),  # yesterday, but after yesterday's 15:00 cut-off
    ]
    history = [_row("2026-09-17", issue_id="a"), _row("2026-09-17", issue_id="b"), _row("2026-09-16", issue_id="a")]
    events = [_event("2026-09-17", "a", "accelerating", (NOW - timedelta(hours=1)).isoformat()),
              _event("2026-09-16", "a", "accelerating", (NOW - timedelta(days=1, hours=1)).isoformat()),
              _event("2026-09-17", "b", "emerging", (NOW - timedelta(hours=1)).isoformat())]
    day = compare_periods(articles, history, events, NOW)[0]
    assert (day.current.articles, day.current.sources, day.current.issues, day.current.accelerations) == (2, 2, 2, 1)
    assert (day.previous.articles, day.previous.sources, day.previous.issues, day.previous.accelerations) == (1, 1, 1, 1)


def test_compare_periods_counts_brand_mentions_when_tags_are_given():
    class _Tag:
        def __init__(self, ts, brands):
            self.ts, self.brands = ts, brands

    tagged = [_Tag(NOW - timedelta(hours=1), ["ACB", "MB"]), _Tag(NOW - timedelta(days=1, hours=1), ["ACB"])]
    day = compare_periods([], [], [], NOW, tagged)[0]
    assert (day.current.mentions, day.previous.mentions) == (2, 1)


def test_compare_periods_returns_day_week_and_month():
    assert [c.current_label for c in compare_periods([], [], [], NOW)] == ["Hôm nay", "Tuần này", "Tháng này"]


# --- media gap (§43) ----------------------------------------------------------
def test_major_sources_are_the_most_active_in_the_last_week():
    articles = [_art("CafeF", NOW - timedelta(hours=i)) for i in range(1, 4)]
    articles += [_art("VnExpress", NOW - timedelta(hours=1))]
    articles += [_art("Cũ", NOW - timedelta(days=30))] * 9  # outside the window
    assert major_sources(articles, NOW, n=2) == ["CafeF", "VnExpress"]


def test_missing_major_sources_lists_only_the_absent_ones_in_order():
    assert missing_major_sources(["CafeF"], ["VnExpress", "CafeF", "Vietstock"]) == ["VnExpress", "Vietstock"]
    assert missing_major_sources(["CafeF"], ["CafeF"]) == []


# --- exports (§45) -------------------------------------------------------------
def test_history_json_has_issues_and_comparisons():
    payload = json.loads(history_json(issue_histories([_row("2026-09-16")]), compare_periods([], [], [], NOW), NOW))
    assert payload["issues"][0]["issue_id"] == "eximbank-tang-von"
    assert [c["current_label"] for c in payload["comparisons"]] == ["Hôm nay", "Tuần này", "Tháng này"]


def test_signals_json_is_ordered_oldest_first():
    events = [_event("2026-09-17", "x", "peak", "2026-09-17T12:00:00+07:00"),
              _event("2026-09-17", "x", "emerging", "2026-09-17T09:00:00+07:00")]
    payload = json.loads(signals_json(events, NOW))
    assert [e["to_status"] for e in payload["events"]] == ["emerging", "peak"]


def test_issues_history_csv_round_trips_with_vietnamese_titles():
    text = issues_history_csv(issue_histories([_row("2026-09-16", title="Lãi suất, tiền gửi")]))
    [row] = list(csv.DictReader(io.StringIO(text)))
    assert row["title"] == "Lãi suất, tiền gửi"  # comma survives quoting
    assert row["total_articles"] == "5"


def test_issues_history_csv_is_just_a_header_when_empty():
    assert issues_history_csv([]).splitlines() == [
        "issue_id,title,first_detected,last_day,days_active,total_articles,max_sources,peak_day,"
        "peak_articles,peak_velocity,best_rank,peak_hot,latest_status"]


# --- previous period not yet covered by collection ------------------------------
def test_previous_period_is_flagged_when_collection_started_inside_it():
    started = NOW - timedelta(days=3)  # data starts mid-week-before... no: only 3 days of data
    articles = [{"source": "A", "title": "t", "url": "u", "published_at": started, "first_seen_at": started}]
    day, week, month = compare_periods(articles, [], [], NOW)
    assert day.previous_covered is True          # yesterday's 00:00 is after the start
    assert week.previous_covered is False        # last Monday predates the start
    assert month.previous_covered is False
    assert week.collection_start == started.date().isoformat()


def test_collection_start_uses_first_seen_not_published_date():
    # An old published date (backfilled/archived feed item) must not pretend
    # the system has been running since then.
    art = {"source": "A", "title": "t", "url": "u", "published_at": NOW - timedelta(days=60),
           "first_seen_at": NOW - timedelta(days=2)}
    assert compare_periods([art], [], [], NOW)[2].previous_covered is False


def test_no_articles_means_nothing_is_covered():
    assert all(c.previous_covered is False for c in compare_periods([], [], [], NOW))

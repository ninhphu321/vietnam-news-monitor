"""Tests for web/analytics.py (data-analytics feature group A)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from web.analytics import (
    collection_lag,
    compute_analytics,
    cooccurrence,
    coverage_gaps,
    first_movers,
    hourly_rhythm,
    reposts,
    topic_mix,
    volume_by_topic,
)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
NOW = datetime(2026, 9, 17, 18, 0, tzinfo=TZ)
TODAY_9 = datetime(2026, 9, 17, 9, 0, tzinfo=TZ)


def _a(source, title, when, seen_after_min=10, url=None):
    return {
        "source": source,
        "title": title,
        "url": url or f"https://x/{source}/{title}/{when.isoformat()}",
        "published_at": when,
        "first_seen_at": when + timedelta(minutes=seen_after_min),
    }


ISSUE_TITLE = "Eximbank tăng vốn điều lệ lên 20.000 tỷ đồng"


# --- 1. first movers -------------------------------------------------------
def test_first_mover_and_lags_for_a_multi_source_issue():
    arts = [
        _a("CafeF", ISSUE_TITLE, TODAY_9),
        _a("VnExpress", ISSUE_TITLE + " (cập nhật)", TODAY_9 + timedelta(minutes=10)),
        _a("Dân Trí", "Cổ đông Eximbank duyệt tăng vốn", TODAY_9 + timedelta(minutes=30)),
    ]
    # the same three outlets again on the previous day, so each has >= 2
    # participations (the leaderboard hides sources with fewer, as noise)
    y = TODAY_9 - timedelta(days=1)
    arts += [
        _a("CafeF", ISSUE_TITLE, y),
        _a("VnExpress", ISSUE_TITLE, y + timedelta(minutes=10)),
        _a("Dân Trí", "Cổ đông Eximbank duyệt tăng vốn", y + timedelta(minutes=30)),
    ]
    rows, today = first_movers(arts, NOW)

    assert len(today) == 1
    assert today[0]["first_source"] == "CafeF"
    assert dict(today[0]["lags"]) == {"VnExpress": 10.0, "Dân Trí": 30.0}
    board = {r.source: r for r in rows}
    assert board["CafeF"].first_count == 2 and board["CafeF"].participated == 2
    assert board["VnExpress"].first_count == 0 and board["VnExpress"].median_lag_min == 10.0


def test_first_movers_ignore_single_source_issues():
    arts = [_a("CafeF", ISSUE_TITLE + f" {i}", TODAY_9 + timedelta(minutes=i)) for i in range(3)]
    rows, today = first_movers(arts, NOW)
    assert rows == [] and today == []


# --- 2. coverage gaps ------------------------------------------------------
def test_exclusive_issue_is_one_source_only():
    arts = [_a("CafeF", ISSUE_TITLE + f" phần {i}", TODAY_9 + timedelta(minutes=i)) for i in range(3)]
    exclusives, gaps = coverage_gaps(arts, NOW)
    assert exclusives and exclusives[0]["source"] == "CafeF" and exclusives[0]["articles"] == 3
    assert gaps == []


def test_gap_lists_major_sources_that_missed_a_wide_issue():
    covering = ["CafeF", "VnExpress", "Dân Trí", "Tuổi Trẻ"]
    arts = [_a(s, ISSUE_TITLE, TODAY_9 + timedelta(minutes=i)) for i, s in enumerate(covering)]
    # an extra major outlet that is active but never mentions the issue
    arts += [_a("Vietstock", f"Chứng khoán phiên {i}", TODAY_9 + timedelta(minutes=i)) for i in range(6)]
    _, gaps = coverage_gaps(arts, NOW)
    assert gaps and gaps[0]["sources"] == 4
    assert "Vietstock" in gaps[0]["missing"]
    assert "CafeF" not in gaps[0]["missing"]


# --- 3. collection lag -----------------------------------------------------
def test_collection_lag_median_and_backfill_exclusion():
    arts = [_a("CafeF", f"Tin số {i}", TODAY_9 + timedelta(minutes=i), seen_after_min=15) for i in range(6)]
    arts.append(_a("CafeF", "Tin backfill cũ", TODAY_9, seen_after_min=60 * 24))  # > 6h: ignored
    rows = collection_lag(arts, NOW)
    assert len(rows) == 1
    assert rows[0].median_min == 15.0 and rows[0].samples == 6


def test_collection_lag_needs_enough_samples():
    arts = [_a("CafeF", f"Tin {i}", TODAY_9 + timedelta(minutes=i)) for i in range(3)]
    assert collection_lag(arts, NOW) == []


# --- 4. hourly rhythm ------------------------------------------------------
def test_hourly_rhythm_peak_hour_and_night_share():
    arts = [_a("CafeF", f"Sáng {i}", TODAY_9.replace(hour=8, minute=i)) for i in range(4)]
    arts += [_a("CafeF", "Khuya", TODAY_9.replace(hour=2))]
    overall, rows = hourly_rhythm(arts, NOW)
    assert overall[8] == 4 and overall[2] == 1
    assert rows[0].peak_hour == 8
    assert rows[0].night_share == pytest.approx(0.2)


# --- 5. volume by topic ----------------------------------------------------
def test_volume_by_topic_counts_per_day():
    yesterday = TODAY_9 - timedelta(days=1)
    arts = [
        _a("CafeF", "Lãi suất huy động tăng", TODAY_9),
        _a("CafeF", "Lãi suất vay giảm", TODAY_9 + timedelta(minutes=5)),
        _a("CafeF", "Giá vàng đi ngang", yesterday),
    ]
    days, totals, topics = volume_by_topic(arts, NOW, days=3)
    assert len(days) == 3 and days[-1] == NOW.date()
    assert totals == [0, 1, 2]
    assert topics["lãi suất"] == [0, 0, 2]
    assert topics["giá vàng"] == [0, 1, 0]


# --- 6. reposts ------------------------------------------------------------
def test_repost_detected_within_same_source_only():
    t = "Vietcombank công bố kế hoạch tăng vốn điều lệ mới"
    arts = [
        _a("CafeF", t, TODAY_9),
        _a("CafeF", t, TODAY_9 + timedelta(hours=2)),        # same source, same day: repost
        _a("VnExpress", t, TODAY_9 + timedelta(hours=1)),    # other source: not a repost
    ] + [_a("CafeF", f"Tin khác {i} về thị trường", TODAY_9 + timedelta(minutes=i)) for i in range(3)]
    stats, examples = reposts(arts, NOW)
    by = {r["source"]: r for r in stats}
    assert by["CafeF"]["reposts"] == 1
    assert "VnExpress" not in by  # too few samples to report
    assert examples and examples[0]["source"] == "CafeF"


def test_daily_template_with_different_dates_is_not_a_repost():
    arts = [
        _a("Vietstock", "Top cổ phiếu đáng chú ý đầu phiên 15/09", TODAY_9 - timedelta(hours=20)),
        _a("Vietstock", "Top cổ phiếu đáng chú ý đầu phiên 16/09", TODAY_9),
    ] + [_a("Vietstock", f"Bản tin khác số {i}", TODAY_9 + timedelta(minutes=i)) for i in range(4)]
    stats, _ = reposts(arts, NOW)
    assert stats[0]["reposts"] == 0


# --- 7. co-occurrence ------------------------------------------------------
def test_cooccurrence_counts_entity_topic_pairs():
    arts = [
        _a("CafeF", "Techcombank tăng vốn điều lệ", TODAY_9),
        _a("VnExpress", "Techcombank tăng vốn lên 100.000 tỷ", TODAY_9),
        _a("Dân Trí", "Techcombank chia cổ tức", TODAY_9),
    ]
    entity_topic, _ = cooccurrence(arts, NOW)
    pairs = {(r["entity"], r["topic"]): r["count"] for r in entity_topic}
    assert pairs[("Techcombank", "tăng vốn")] == 2


# --- 8. topic mix ----------------------------------------------------------
def test_topic_mix_shares_per_source():
    arts = [_a("CafeF", f"Lãi suất kỳ hạn {i}", TODAY_9 + timedelta(minutes=i)) for i in range(4)]
    arts += [_a("CafeF", "Chuyện khác hoàn toàn", TODAY_9)]
    topics, matrix, totals = topic_mix(arts, NOW)
    assert matrix["CafeF"]["lãi suất"] == pytest.approx(0.8)
    assert totals["CafeF"] == 5


# --- bundle ----------------------------------------------------------------
def test_compute_analytics_rejects_naive_now():
    with pytest.raises(ValueError):
        compute_analytics([], datetime(2026, 9, 17, 18, 0))


def test_compute_analytics_on_empty_input_is_safe():
    an = compute_analytics([], NOW)
    assert an.first_mover_rows == [] and an.exclusives == [] and an.lag_rows == []

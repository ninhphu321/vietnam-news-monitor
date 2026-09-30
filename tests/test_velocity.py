from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from web.signals import ACCELERATING, COOLING, EMERGING, PEAK
from web.velocity import calculate_velocity

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
NOW = datetime(2026, 9, 14, 12, 0, tzinfo=TZ)


def _ts(*minutes_ago):
    return [NOW - timedelta(minutes=m) for m in minutes_ago]


def test_requires_timezone_aware_now():
    with pytest.raises(ValueError):
        calculate_velocity([], datetime(2026, 9, 14, 12, 0))


def test_both_windows_empty_is_cooling():
    result = calculate_velocity(_ts(200, 210), NOW, window=timedelta(hours=1))
    assert result.status == COOLING
    assert result.current_rate == 0.0
    assert result.previous_rate == 0.0


def test_current_window_only_is_emerging():
    # 3 articles in the last hour, nothing at all in the hour before that.
    result = calculate_velocity(_ts(5, 20, 45), NOW, window=timedelta(hours=1))
    assert result.status == EMERGING
    assert result.current_rate == 3.0
    assert result.previous_rate == 0.0


def test_current_faster_than_previous_is_accelerating():
    # previous hour: 2 articles: 1 bài/giờ; current hour: 6 articles.
    result = calculate_velocity(_ts(70, 90, 5, 15, 25, 35, 45, 55), NOW, window=timedelta(hours=1))
    assert result.previous_rate == 2.0
    assert result.current_rate == 6.0
    assert result.status == ACCELERATING


def test_current_slower_than_previous_is_cooling():
    # previous hour: 6 articles; current hour: 1 article.
    result = calculate_velocity(_ts(30, 70, 75, 80, 85, 90, 95), NOW, window=timedelta(hours=1))
    assert result.previous_rate == 6.0
    assert result.current_rate == 1.0
    assert result.status == COOLING


def test_stable_rate_is_peak():
    # 2 articles/hour in both windows -> ratio 1.0, within +-15%.
    result = calculate_velocity(_ts(10, 40, 70, 100), NOW, window=timedelta(hours=1))
    assert result.previous_rate == result.current_rate == 2.0
    assert result.status == PEAK


def test_window_is_configurable():
    # A 30-minute window: only the most recent 30 minutes counts as
    # "current" even though the same articles would all land in
    # "current" under the default 1h window.
    result = calculate_velocity(_ts(5, 10, 40), NOW, window=timedelta(minutes=30))
    assert result.current_rate == 4.0  # 2 articles / 0.5h
    assert result.previous_rate == 2.0  # 1 article / 0.5h

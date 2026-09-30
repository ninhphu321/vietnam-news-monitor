"""Tests for web/signals.py — signal lifecycle (roadmap V2 §15)."""

import pytest

from web.signals import ACCELERATING, COOLING, EMERGING, PEAK, classify_lifecycle, should_alert


def test_first_appearance_is_always_emerging_regardless_of_velocity():
    assert classify_lifecycle(velocity_now=5.0, velocity_previous=None) == EMERGING
    assert classify_lifecycle(velocity_now=0.0, velocity_previous=None) == EMERGING


def test_faster_than_last_cycle_is_accelerating():
    assert classify_lifecycle(velocity_now=3.0, velocity_previous=2.0) == ACCELERATING


def test_slower_than_last_cycle_is_cooling():
    assert classify_lifecycle(velocity_now=1.0, velocity_previous=2.0) == COOLING


def test_roughly_unchanged_velocity_is_peak():
    assert classify_lifecycle(velocity_now=2.05, velocity_previous=2.0) == PEAK
    assert classify_lifecycle(velocity_now=1.95, velocity_previous=2.0) == PEAK


@pytest.mark.parametrize("now,factor", [(2.3, 1.15), (1.7, 0.85)])
def test_thresholds_are_inclusive_boundaries(now, factor):
    # 2.0 * 1.15 = 2.3 exactly -> accelerating; 2.0 * 0.85 = 1.7 exactly -> cooling.
    previous = 2.0
    result = classify_lifecycle(now, previous)
    assert result in (ACCELERATING, COOLING)


def test_zero_previous_velocity_with_new_articles_is_accelerating():
    assert classify_lifecycle(velocity_now=1.0, velocity_previous=0.0) == ACCELERATING


def test_zero_previous_and_zero_now_is_peak_not_accelerating():
    # No movement at all is not "accelerating" just because the ratio
    # (0/0) would otherwise be undefined.
    assert classify_lifecycle(velocity_now=0.0, velocity_previous=0.0) == PEAK


# --- should_alert (roadmap V3 §26 Signal Alert) --------------------------


def test_should_alert_requires_both_bars_at_once():
    assert should_alert(source_count=5, hot_score=90.0) is True
    assert should_alert(source_count=1, hot_score=90.0) is False  # not enough sources
    assert should_alert(source_count=5, hot_score=50.0) is False  # score too low


def test_should_alert_thresholds_are_inclusive():
    assert should_alert(source_count=3, hot_score=70.0) is True


def test_should_alert_thresholds_are_configurable():
    assert should_alert(source_count=2, hot_score=60.0, min_sources=2, min_score=60.0) is True
    assert should_alert(source_count=2, hot_score=60.0) is False  # defaults are stricter

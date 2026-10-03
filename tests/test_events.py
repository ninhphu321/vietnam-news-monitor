"""Tests for web/events.py — Information Events, evidence and the Daily
Briefing (roadmap V6 phase 1)."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from web.events import (MEDIA_SIGNAL, OFFICIAL_SIGNAL, build_briefing, build_event, build_events,
                        evidence_for)
from web.issues import Issue
from web.signals import ACCELERATING, EMERGING, PEAK
from web.source_registry import load_source_registry, type_for
from web.velocity import VelocityResult

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
T0 = datetime(2026, 10, 3, 9, 0, tzinfo=TZ)
REGISTRY = {"Chính phủ": {"type": "OFFICIAL"}, "VnExpress": {"type": "MEDIA"}, "CafeF": {"type": "MEDIA"}}


def _issue(issue_id="eximbank-nhan-su", title="Eximbank · Nhân sự lãnh đạo", sources=("VnExpress", "CafeF"),
           articles=None, hot=80.0, velocity_1h=None, entities=("eximbank",)):
    if articles is None:
        articles = [{"title": "t", "url": f"u{i}", "source": s, "ts": T0 + timedelta(minutes=10 * i)}
                    for i, s in enumerate(sources)]
    return Issue(
        issue_id=issue_id, issue_title=title, entities=list(entities), topics=["nhân sự lãnh đạo"],
        article_count=len(articles), unique_source_count=len(sources), first_seen_at=T0, last_seen_at=T0,
        velocity=1.0, acceleration=1.0, volume_score=50.0, source_score=50.0, velocity_score=50.0,
        novelty_score=50.0, source_weight_score=100.0, hot_score=hot, sources=list(sources),
        all_articles=articles, velocity_1h=velocity_1h,
    )


def _accel(acc=2.0):
    return VelocityResult(current_rate=4.0, previous_rate=2.0, acceleration=acc, status=ACCELERATING)


# --- source types -----------------------------------------------------------------
def test_type_for_defaults_to_media_and_ignores_unknown_types():
    assert type_for("Nguồn lạ", {}) == "MEDIA"
    assert type_for("X", {"X": {"type": "NONSENSE"}}) == "MEDIA"
    assert type_for("Chính phủ", REGISTRY) == "OFFICIAL"


def test_shipped_registry_marks_only_the_government_portal_official():
    from config import BASE_DIR
    registry = load_source_registry(BASE_DIR / "source_registry.json")
    assert [s for s in registry if type_for(s, registry) == "OFFICIAL"] == ["Chính phủ"]
    assert len(registry) == 23


# --- evidence (§52) ----------------------------------------------------------------
def test_evidence_separates_official_from_media_and_finds_the_first_media_report():
    articles = [
        {"title": "a", "url": "1", "source": "CafeF", "ts": T0 + timedelta(minutes=30)},
        {"title": "b", "url": "2", "source": "VnExpress", "ts": T0 + timedelta(minutes=5)},
        {"title": "c", "url": "3", "source": "Chính phủ", "ts": T0},  # official, earliest of all
    ]
    ev = evidence_for(_issue(sources=("CafeF", "VnExpress", "Chính phủ"), articles=articles), REGISTRY)
    assert ev.official_sources == ["Chính phủ"] and ev.has_official
    assert ev.media_sources == ["CafeF", "VnExpress"]
    # "first media report" ignores the official article even though it came first
    assert (ev.first_report_source, ev.first_report_at) == ("VnExpress", T0 + timedelta(minutes=5))
    assert ev.first_official_at == T0


def test_evidence_with_no_official_source_says_so():
    ev = evidence_for(_issue(), REGISTRY)
    assert ev.official_sources == [] and not ev.has_official


def test_evidence_tolerates_articles_without_timestamps():
    ev = evidence_for(_issue(articles=[{"title": "a", "url": "1", "source": "CafeF"}]), REGISTRY)
    assert ev.first_report_at is None and ev.first_report_source is None


# --- events and signal types (§51, §53) --------------------------------------------
def test_event_splits_entity_from_event_type():
    e = build_event(_issue(), REGISTRY)
    assert (e.entity, e.event_type) == ("Eximbank", "Nhân sự lãnh đạo")


def test_topic_only_issue_has_no_entity():
    e = build_event(_issue(title="Khối ngoại · Mua ròng", entities=()), REGISTRY)
    assert e.entity is None and e.event_type == "Khối ngoại · Mua ròng"


def test_media_only_event_is_a_media_signal():
    assert build_event(_issue(), REGISTRY).signal_types == [MEDIA_SIGNAL]


def test_official_plus_media_carries_both_signal_types():
    issue = _issue(sources=("Chính phủ", "CafeF"))
    assert build_event(issue, REGISTRY).signal_types == [OFFICIAL_SIGNAL, MEDIA_SIGNAL]


def test_high_attention_needs_official_source_and_accelerating_media():
    official = _issue(sources=("Chính phủ", "CafeF"))
    assert build_event(official, REGISTRY, ACCELERATING).high_attention is True
    assert build_event(official, REGISTRY, PEAK).high_attention is False          # official but not accelerating
    assert build_event(_issue(), REGISTRY, ACCELERATING).high_attention is False  # accelerating but no official source


def test_high_attention_also_triggers_on_the_fixed_window_velocity():
    issue = _issue(sources=("Chính phủ", "CafeF"), velocity_1h=_accel())
    assert build_event(issue, REGISTRY, PEAK).high_attention is True


# --- daily briefing (§56) ----------------------------------------------------------
def _history(day, title):
    return {"day": day, "title": title, "issue_id": title}


def test_briefing_has_the_five_fixed_slots_in_order():
    items = build_briefing([], [], date(2026, 10, 3))
    assert [i.key for i in items] == ["emerging", "accelerating", "broadest", "new_entity", "official"]
    assert all(i.event is None and i.empty_note for i in items)


def test_briefing_picks_the_right_event_for_each_slot():
    emerging = build_event(_issue("a", "Alpha · X", hot=60.0), REGISTRY, EMERGING)
    fast = build_event(_issue("b", "Beta · Y", hot=70.0, velocity_1h=_accel(3.0)), REGISTRY, ACCELERATING)
    wide = build_event(_issue("c", "Gamma · Z", sources=("VnExpress", "CafeF", "Chính phủ"), hot=50.0,
                              articles=[{"title": "t", "url": "9", "source": "Chính phủ", "ts": T0}]), REGISTRY, PEAK)
    history = [_history("2026-10-01", "Alpha · X"), _history("2026-10-01", "Beta · Y")]  # Gamma is new
    by_key = {i.key: i.event for i in build_briefing([emerging, fast, wide], history, date(2026, 10, 3))}
    assert by_key["emerging"].issue_id == "a"
    assert by_key["accelerating"].issue_id == "b"
    assert by_key["broadest"].issue_id == "c"
    assert by_key["new_entity"].issue_id == "c"
    assert by_key["official"].issue_id == "c"


def test_new_entity_cannot_be_judged_without_earlier_history():
    e = build_event(_issue(), REGISTRY, EMERGING)
    item = next(i for i in build_briefing([e], [], date(2026, 10, 3)) if i.key == "new_entity")
    assert item.event is None and "lịch sử" in item.empty_note
    # today's own rows must not count as "earlier history"
    item = next(i for i in build_briefing([e], [_history("2026-10-03", "Eximbank · X")], date(2026, 10, 3))
                if i.key == "new_entity")
    assert item.event is None and "lịch sử" in item.empty_note


def test_entity_seen_on_an_earlier_day_is_not_new():
    e = build_event(_issue(), REGISTRY, EMERGING)
    history = [_history("2026-10-01", "Eximbank · Tăng vốn")]
    item = next(i for i in build_briefing([e], history, date(2026, 10, 3)) if i.key == "new_entity")
    assert item.event is None and "mới" in item.empty_note


def test_briefing_slot_without_official_source_says_none_detected():
    e = build_event(_issue(), REGISTRY, PEAK)
    item = next(i for i in build_briefing([e], [], date(2026, 10, 3)) if i.key == "official")
    assert item.event is None and "Chưa phát hiện" in item.empty_note


def test_build_events_applies_lifecycle_per_issue():
    events = build_events([_issue("a"), _issue("b")], REGISTRY, {"a": EMERGING})
    assert [e.lifecycle_status for e in events] == [EMERGING, None]

"""Rendering/export tests for the V6 phase-1 pieces: the evidence line on
issue cards, the Daily Briefing page and events.json."""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from models import NewsItem
from tests.test_events import REGISTRY, T0, _accel, _history, _issue
from web.events import build_briefing, build_event, build_events
from web.exports import events_json
from web.generate_site import _evidence_html, build_site, render_briefing_page, render_day_page, render_radar_page
from web.signals import ACCELERATING, EMERGING, PEAK

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
NOW = datetime(2026, 10, 3, 15, 0, tzinfo=TZ)


# --- evidence line -----------------------------------------------------------------
def test_evidence_line_lists_media_count_first_report_and_no_official():
    html = _evidence_html(build_event(_issue(), REGISTRY))
    assert "nguồn chính thống: chưa phát hiện tiêu đề khớp" in html
    assert "truyền thông: 2 nguồn" in html
    assert "báo đầu tiên: VnExpress 09:00" in html
    assert "chú ý cao" not in html


def test_evidence_line_names_the_official_source_and_flags_high_attention():
    event = build_event(_issue(sources=("Chính phủ", "CafeF")), REGISTRY, ACCELERATING)
    html = _evidence_html(event)
    assert "nguồn chính thống: có (Chính phủ)" in html
    assert "chú ý cao" in html and "Không phải dự báo" in html  # the caveat travels with the label


def test_evidence_line_is_empty_without_an_event():
    assert _evidence_html(None) == ""


def test_issue_card_shows_evidence_only_when_events_are_given():
    issue = _issue()
    day = date(2026, 10, 3)
    with_ev = render_day_page(day, {}, [day], trending=[issue], events_by_id={issue.issue_id: build_event(issue, REGISTRY)})
    without = render_day_page(day, {}, [day], trending=[issue])
    assert '<div class="evidence">' in with_ev
    assert '<div class="evidence">' not in without  # the CSS rule is always present; the element is not


def test_radar_cards_show_evidence_too():
    issue = _issue()
    html = render_radar_page([issue], {}, True, NOW, None, {issue.issue_id: build_event(issue, REGISTRY)})
    assert '<div class="evidence">' in html


# --- briefing page -----------------------------------------------------------------
def test_briefing_page_renders_five_numbered_slots():
    html = render_briefing_page(build_briefing([], [], NOW.date()), True, NOW)
    for n in ("01", "02", "03", "04", "05"):
        assert f'issue-rank">{n}<' in html
    assert "Bản tin hôm nay" in html and "không phải dự báo thị trường" in html


def test_briefing_page_shows_event_details_and_empty_notes():
    emerging = build_event(_issue(sources=("Chính phủ", "CafeF")), REGISTRY, EMERGING)
    html = render_briefing_page(build_briefing([emerging], [_history("2026-10-01", "Khác · X")], NOW.date()), True, NOW)
    assert "<b>Eximbank · Nhân sự lãnh đạo</b>" in html
    assert "<span>chính thống + truyền thông</span>" in html  # signal types: official first, then media
    assert "Hiện không có vấn đề nào đang tăng tốc." in html  # an empty slot says so instead of being padded


def test_briefing_page_escapes_event_titles():
    bad = build_event(_issue(title='X<script>alert(1)</script> · Y'), REGISTRY, EMERGING)
    html = render_briefing_page(build_briefing([bad], [], NOW.date()), True, NOW)
    assert "<script>alert(1)</script>" not in html


# --- build_site / exports ---------------------------------------------------------
def test_build_site_writes_briefing_page_and_events_json(tmp_path, db):
    db.insert_if_new(NewsItem("VnExpress", "Tin thường", "https://x/1", datetime(2026, 10, 1, 10, 0, tzinfo=TZ)))
    out_dir = tmp_path / "site"
    build_site(db, out_dir=out_dir)

    assert "Bản tin hôm nay" in (out_dir / "briefing.html").read_text(encoding="utf-8")
    payload = json.loads((out_dir / "events.json").read_text(encoding="utf-8"))
    assert payload["events"] == [] and len(payload["briefing"]) == 5


def test_events_json_carries_evidence_and_briefing_slots():
    official = _issue("a", sources=("Chính phủ", "CafeF"))
    events = build_events([official], REGISTRY, {"a": ACCELERATING})
    payload = json.loads(events_json(events, build_briefing(events, [], NOW.date()), NOW))
    [e] = payload["events"]
    assert e["id"] == "a" and e["entity"] == "Eximbank" and e["high_attention"] is True
    assert e["signal_types"] == ["OFFICIAL_SIGNAL", "MEDIA_SIGNAL"]
    assert e["evidence"]["official_sources"] == ["Chính phủ"]
    assert e["evidence"]["first_report_source"] == "CafeF"
    slots = {b["slot"]: b["event_id"] for b in payload["briefing"]}
    assert slots["official"] == "a" and slots["broadest"] == "a" and slots["emerging"] is None


def test_events_json_handles_missing_times():
    issue = _issue(articles=[{"title": "a", "url": "1", "source": "CafeF"}], sources=("CafeF",))
    events = build_events([issue], REGISTRY)
    e = json.loads(events_json(events, [], NOW))["events"][0]
    assert e["evidence"]["first_report_at"] is None

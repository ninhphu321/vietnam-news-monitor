"""Tests for web/issues.py (Issue Intelligence V3). Section numbers in
comments refer to PROJECT_SPEC_V3_ISSUE_INTELLIGENCE.md's own test
list (section 16) so each spec test case maps to exactly one test
here.
"""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from web.issues import (
    Issue,
    _entity_display,
    _extract_entities,
    _extract_topics,
    _issue_keys,
    top_issues,
)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
TODAY_9AM = datetime(2026, 9, 17, 9, 0, tzinfo=TZ)


def _article(source, title, url, when):
    return {"source": source, "title": title, "url": url, "published_at": when, "first_seen_at": when}


# --- Entity/topic extraction primitives --------------------------------

def test_extract_entities_requires_all_caps_or_long_capitalized_word():
    assert "eximbank" in _extract_entities("Eximbank gia hạn đề cử nhân sự HĐQT")
    # "HĐQT" is all-caps but a generic role/institution term (every
    # company has a board), not a specific entity - see
    # _GENERIC_ACRONYMS and the false-merge regression test below.
    assert "hđqt" not in _extract_entities("Eximbank gia hạn đề cử nhân sự HĐQT")
    # "Trung" (Trung Quốc) is a short capitalized fragment, not a name.
    assert "trung" not in _extract_entities("Trung Quốc muốn đầu tư năng lượng")


def test_extract_topics_matches_curated_triggers():
    assert "lãi suất" in _extract_topics("Ngân hàng A tăng lãi suất huy động")
    assert "nhân sự lãnh đạo" in _extract_topics("Eximbank gia hạn đề cử nhân sự HĐQT")


def test_issue_keys_empty_when_only_entity_or_only_one_topic_present():
    """A bare entity or a single bare topic must never form an issue key
    on its own (spec section 3) — only an entity+topic or topic+topic
    pairing does."""
    assert _issue_keys("Eximbank tổ chức sự kiện tri ân khách hàng") == set()
    assert _issue_keys("Giá vàng biến động trong phiên sáng") == set()


# --- Spec section 16, Test 1: Same Issue --------------------------------

def test_same_issue_different_wording_merges_into_one():
    articles = [
        _article("VnExpress", "Eximbank gia hạn đề cử nhân sự HĐQT", "u1", TODAY_9AM),
        _article("CafeF", "Eximbank hoãn ngày chốt danh sách ứng viên HĐQT", "u2", TODAY_9AM + timedelta(hours=1)),
        _article("Tuổi Trẻ", "Cổ đông chất vấn Eximbank về kế hoạch nhân sự", "u3", TODAY_9AM + timedelta(hours=2)),
    ]
    issues = top_issues(articles, TODAY_9AM + timedelta(hours=2), min_articles=3, min_sources=2)

    assert len(issues) == 1
    assert issues[0].article_count == 3
    assert issues[0].unique_source_count == 3
    assert "Eximbank" in issues[0].issue_title


# --- Regression: generic acronym ("HĐQT") wrongly treated as an entity --

def test_generic_role_acronym_does_not_falsely_merge_unrelated_companies():
    """Live-data bug found 2026-09-16: "HĐQT" (Hội đồng quản trị - every
    company has one) is all-caps and used to satisfy the acronym branch
    of _extract_entities, so an Eximbank board-nomination story and an
    unrelated ex-football-coach-joins-a-port-company's-board story got
    merged into one fake "HĐQT · Nhân sự lãnh đạo" issue purely because
    both headlines say "HĐQT". They must stay separate: no shared real
    entity, and the port company is never even named."""
    articles = [
        _article("Vietstock", "Trước thềm ĐHĐCĐ bất thường, Eximbank gia hạn đề cử nhân sự HĐQT",
                  "u1", TODAY_9AM),
        _article("FiLi", "Eximbank gia hạn đề cử nhân sự HĐQT", "u2", TODAY_9AM + timedelta(hours=1)),
        _article("Dân Trí", "Cựu HLV trưởng bóng đá Việt Nam tham gia HĐQT một công ty khai thác cảng",
                  "u3", TODAY_9AM + timedelta(hours=2)),
    ]
    issues = top_issues(articles, TODAY_9AM + timedelta(hours=2), min_articles=2, min_sources=1)

    titles = {i.issue_title.lower() for i in issues}
    assert not any("hđqt" in t and "eximbank" not in t for t in titles)
    assert all("cảng" not in t for t in titles)


# --- Spec section 16, Test 2: Same Entity, Different Issues -------------

def test_same_entity_different_topics_stay_separate_issues():
    now = TODAY_9AM + timedelta(hours=3)
    articles = [
        _article("VnExpress", "Vietcombank tăng lãi suất huy động kỳ hạn dài", "u1", TODAY_9AM),
        _article("CafeF", "Vietcombank điều chỉnh lãi suất tiết kiệm", "u2", TODAY_9AM),
        _article("Tuổi Trẻ", "Vietcombank tuyển dụng hàng loạt vị trí mới", "u3", TODAY_9AM),
        _article("Znews", "Vietcombank tuyển dụng thực tập sinh 2026", "u4", TODAY_9AM),
        _article("Dân Trí", "Vietcombank mở chi nhánh mới tại Cần Thơ", "u5", TODAY_9AM),
        _article("VTV", "Vietcombank khai trương chi nhánh tại Cần Thơ", "u6", TODAY_9AM),
    ]
    issues = top_issues(articles, now, min_articles=2, min_sources=2)
    titles = {i.issue_title.lower() for i in issues}

    assert len(issues) == 3  # lãi suất / tuyển dụng / chi nhánh, not merged
    assert any("lãi suất" in t for t in titles)
    assert any("tuyển dụng" in t for t in titles)
    assert any("chi nhánh" in t for t in titles)


# --- Spec section 16, Test 3: Same Topic, Different Issues --------------

def test_same_topic_different_entities_not_auto_merged():
    now = TODAY_9AM + timedelta(hours=1)
    articles = [
        _article("VnExpress", "Ngân hàng Eximbank tăng lãi suất huy động", "u1", TODAY_9AM),
        _article("CafeF", "Eximbank điều chỉnh biểu lãi suất tiết kiệm", "u2", TODAY_9AM),
        _article("Tuổi Trẻ", "Vietcombank tăng lãi suất huy động kỳ hạn ngắn", "u3", TODAY_9AM),
        _article("Znews", "Vietcombank điều chỉnh lãi suất tiền gửi", "u4", TODAY_9AM),
    ]
    issues = top_issues(articles, now, min_articles=2, min_sources=2)

    assert len(issues) == 2
    assert {i.entities[0] for i in issues} == {"eximbank", "vietcombank"}
    for issue in issues:
        assert issue.article_count == 2


# --- Spec section 16, Test 4: Source Diversity --------------------------

def test_source_diversity_produces_different_source_scores():
    now = TODAY_9AM + timedelta(hours=1)
    # Same article_count (2), very different source spread.
    few_sources = [
        _article("VnExpress", "Eximbank thông báo kế hoạch tăng vốn điều lệ", "u1", TODAY_9AM),
        _article("VnExpress", "Eximbank cập nhật lộ trình tăng vốn điều lệ", "u2", TODAY_9AM),
    ]
    many_sources = [
        _article("CafeF", "Vietcombank công bố kế hoạch tăng vốn điều lệ", "u3", TODAY_9AM),
        _article("Tuổi Trẻ", "Vietcombank chốt phương án tăng vốn điều lệ", "u4", TODAY_9AM),
    ]
    issues = top_issues(few_sources + many_sources, now, min_articles=2, min_sources=1)
    by_entity = {i.entities[0]: i for i in issues}

    assert by_entity["eximbank"].unique_source_count == 1
    assert by_entity["vietcombank"].unique_source_count == 2
    assert by_entity["vietcombank"].source_score > by_entity["eximbank"].source_score


# --- Spec section 16, Test 5: Volume Bias -------------------------------

def test_one_source_many_articles_does_not_dominate_ranking():
    now = TODAY_9AM + timedelta(hours=2)
    # Source A alone posts 4 near-duplicate updates about itself —
    # slightly more raw articles than the diverse issue below, but all
    # from the one source.
    volume_heavy = [
        _article("A", f"Vietcombank cập nhật tăng vốn điều lệ lần {i}", f"va{i}", TODAY_9AM)
        for i in range(4)
    ]
    # 3 different sources, fewer articles, about a different issue.
    diverse = [
        _article("B", "Eximbank tăng lãi suất huy động", "e1", TODAY_9AM),
        _article("C", "Eximbank điều chỉnh lãi suất tiết kiệm", "e2", TODAY_9AM),
        _article("D", "Eximbank công bố biểu lãi suất mới", "e3", TODAY_9AM),
    ]
    issues = top_issues(volume_heavy + diverse, now, min_articles=2, min_sources=1)
    by_entity = {i.entities[0]: i for i in issues}

    assert by_entity["vietcombank"].article_count == 4
    assert by_entity["eximbank"].article_count == 3
    # The single-source issue's source_score must be sharply penalized
    # relative to its own volume_score — the actual anti-bias mechanism
    # (spec section 8: combine volume + source + velocity, don't let
    # raw article count alone decide).
    vcb = by_entity["vietcombank"]
    assert vcb.source_score < vcb.volume_score
    # With only a modest volume edge (4 vs 3, one extra near-duplicate
    # update), the 3-source issue's combined score still comes out
    # ahead — demonstrating the combination does real work rather than
    # being a cosmetic tie-breaker only.
    assert by_entity["eximbank"].hot_score > vcb.hot_score


# --- Spec section 16, Test 6: Why Hot ------------------------------------

def test_why_hot_bullets_trace_to_real_metrics():
    now = TODAY_9AM + timedelta(hours=2)
    articles = [
        _article("VnExpress", "Eximbank tăng lãi suất huy động", "u1", TODAY_9AM),
        _article("CafeF", "Eximbank điều chỉnh lãi suất tiết kiệm", "u2", TODAY_9AM),
        _article("Tuổi Trẻ", "Eximbank công bố biểu lãi suất mới", "u3", TODAY_9AM + timedelta(hours=1, minutes=45)),
    ]
    issues = top_issues(articles, now, min_articles=3, min_sources=2)

    assert len(issues) == 1
    why = issues[0].why_hot
    assert any(str(issues[0].unique_source_count) in b for b in why)
    assert any(str(issues[0].article_count) in b for b in why)
    assert 2 <= len(why) <= 4


# --- Spec section 16, Test 7: Ranking Stability -------------------------

def test_one_extra_article_does_not_flip_an_established_ranking():
    now = TODAY_9AM + timedelta(hours=4)
    established = [
        _article("VnExpress", "Eximbank tăng lãi suất huy động kỳ hạn dài", "e1", TODAY_9AM),
        _article("CafeF", "Eximbank điều chỉnh biểu lãi suất tiết kiệm", "e2", TODAY_9AM),
        _article("Tuổi Trẻ", "Eximbank công bố lãi suất mới cho khách VIP", "e3", TODAY_9AM),
        _article("Znews", "Eximbank tăng lãi suất thêm một đợt nữa", "e4", TODAY_9AM),
    ]
    newcomer = [
        _article("A", "Vietcombank tuyển dụng nhân sự mới", "v1", now),
    ]
    before = top_issues(established, now, min_articles=2, min_sources=2)
    after = top_issues(established + newcomer, now, min_articles=2, min_sources=2)

    # The newcomer has only 1 article / 1 source -> never clears the
    # threshold, so it must not appear or disturb the #1 spot at all.
    assert before[0].issue_id == after[0].issue_id
    assert len(after) == len(before)


# --- Spec section 16, Test 8: Timezone -----------------------------------

def test_only_todays_articles_count_toward_the_ranking():
    now = datetime(2026, 9, 17, 8, 0, tzinfo=TZ)
    yesterday_late = datetime(2026, 9, 16, 23, 30, tzinfo=TZ)  # < 24h ago, but NOT "today"
    articles = [
        _article("VnExpress", "Eximbank tăng lãi suất huy động", "u1", yesterday_late),
        _article("CafeF", "Eximbank điều chỉnh biểu lãi suất tiết kiệm", "u2", yesterday_late),
        _article("Tuổi Trẻ", "Eximbank công bố lãi suất mới", "u3", yesterday_late),
    ]
    issues = top_issues(articles, now, min_articles=2, min_sources=2)
    assert issues == []  # all 3 articles are from yesterday (VN calendar day), not today


# --- Component/UI-facing details ----------------------------------------

def test_entity_display_recovers_original_casing():
    assert _entity_display("eximbank", ["Eximbank, HOSE: EIB công bố thông tin"]) == "Eximbank"


def test_representative_articles_capped_at_three_but_all_articles_keeps_everything():
    now = TODAY_9AM + timedelta(hours=1)
    articles = [
        _article(f"S{i}", f"Eximbank thông báo lãi suất mới đợt {i}", f"u{i}", TODAY_9AM)
        for i in range(5)
    ]
    issues = top_issues(articles, now, min_articles=3, min_sources=2)

    assert len(issues) == 1
    assert len(issues[0].representative_articles) == 3
    assert len(issues[0].all_articles) == 5


def test_rejects_naive_now_instead_of_silently_using_the_wrong_clock():
    naive_now = datetime(2026, 9, 17, 9, 0)  # no tzinfo
    with pytest.raises(ValueError):
        top_issues([], naive_now)


def test_thresholds_are_configurable():
    """Spec section 10: "Threshold phải configurable." A 1-article,
    1-source pair must be reachable by loosening both thresholds, and
    unreachable at the defaults."""
    now = TODAY_9AM + timedelta(hours=1)
    articles = [_article("VnExpress", "Eximbank tăng lãi suất huy động", "u1", TODAY_9AM)]

    assert top_issues(articles, now) == []
    loosened = top_issues(articles, now, min_articles=1, min_sources=1)
    assert len(loosened) == 1
    assert loosened[0].article_count == 1


def test_hot_score_components_are_each_0_to_100():
    now = TODAY_9AM + timedelta(hours=1)
    articles = [
        _article("VnExpress", "Eximbank tăng lãi suất huy động", "u1", TODAY_9AM),
        _article("CafeF", "Eximbank điều chỉnh biểu lãi suất tiết kiệm", "u2", TODAY_9AM),
    ]
    issues = top_issues(articles, now, min_articles=2, min_sources=2)

    assert len(issues) == 1
    i = issues[0]
    for score in (i.volume_score, i.source_score, i.velocity_score, i.novelty_score, i.hot_score):
        assert 0 <= score <= 100

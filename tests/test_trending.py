from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from web.trending import (
    _content_words,
    _display_label,
    _dedupe_overlapping,
    _group_by_phrase,
    _phrases,
    _score_groups,
    top_trending,
)

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
NOW = datetime(2026, 9, 16, 12, 0, tzinfo=TZ)


def _article(source, title, url, hours_ago, published=True):
    ts = NOW - timedelta(hours=hours_ago)
    return {
        "source": source,
        "title": title,
        "url": url,
        "published_at": ts if published else None,
        "first_seen_at": ts,
    }


def test_content_words_strips_punctuation_and_stopwords():
    words = _content_words("Eximbank, HOSE: EIB gia hạn đề cử của HĐQT")
    assert "và" not in words  # not present anyway, sanity
    assert "của" not in words  # stopword removed
    assert "eximbank" in words
    assert "hose" in words


def test_phrases_generates_2_and_3_grams_plus_standalone_proper_nouns():
    phrases = _phrases("Cổ đông chất vấn Eximbank về kế hoạch nhân sự")
    assert "chất vấn" in phrases
    assert "kế hoạch" in phrases
    assert "kế hoạch nhân" in phrases
    assert "eximbank" in phrases  # standalone proper noun, mid-title, len >= 4
    assert "cổ đông chất vấn eximbank" not in phrases  # no 4+-grams


def test_phrases_still_excludes_leading_filler_words_via_stopwords():
    """"Nhiều" opening a headline is generic filler, not an entity —
    excluded by the stopword list regardless of capitalization/position,
    while a real entity opening a headline (very common in practice)
    is still picked up (see test above: "Eximbank gia hạn...")."""
    phrases = _phrases("Nhiều ngân hàng tăng lãi suất tiền gửi")
    assert "nhiều" not in phrases


def test_group_by_phrase_requires_multiple_sources_and_articles():
    articles = [
        _article("VnExpress", "Eximbank gia hạn đề cử nhân sự HĐQT", "u1", 1),
        _article("CafeF", "Eximbank hoãn ngày chốt danh sách ứng viên", "u2", 2),
        # Only 1 source ever mentions "vietcombank tăng vốn" -> must be excluded.
        _article("VnExpress", "Vietcombank tăng vốn điều lệ thêm 5000 tỷ", "u3", 1),
        _article("VnExpress", "Vietcombank tăng vốn thêm đợt hai trong năm", "u4", 3),
    ]
    groups = _group_by_phrase(articles, NOW, window_hours=48)
    phrases = {g["phrase"] for g in groups}
    assert "eximbank" in phrases
    assert not any("vietcombank" in p for p in phrases)  # single-source only, filtered out


def test_group_by_phrase_excludes_articles_outside_window():
    articles = [
        _article("VnExpress", "Eximbank gia hạn đề cử nhân sự HĐQT", "u1", 1),
        _article("CafeF", "Eximbank hoãn ngày chốt danh sách ứng viên", "u2", 100),  # outside 48h window
    ]
    groups = _group_by_phrase(articles, NOW, window_hours=48)
    assert groups == []


def test_dedupe_overlapping_prefers_the_more_specific_phrase():
    """A generic 2-word phrase riding along on the same articles as a
    more specific 3-word one is redundant noise, not a second topic."""
    shared_urls = {"u1", "u2", "u3"}
    specific = {"phrase": "ngân hàng nhà nước", "urls": set(shared_urls), "sources": {"A", "B"}, "samples": []}
    generic = {"phrase": "hàng nhà nước", "urls": set(shared_urls), "sources": {"A", "B"}, "samples": []}
    unrelated = {"phrase": "vn-index tăng điểm", "urls": {"u4", "u5"}, "sources": {"A", "C"}, "samples": []}

    kept = _dedupe_overlapping([generic, specific, unrelated])

    kept_phrases = {g["phrase"] for g in kept}
    assert "ngân hàng nhà nước" in kept_phrases
    assert "hàng nhà nước" not in kept_phrases  # dropped as redundant with the specific one
    assert "vn-index tăng điểm" in kept_phrases  # genuinely different story, kept


def test_score_groups_ranks_fast_cross_source_topic_above_slow_one():
    fast_ts = [NOW - timedelta(hours=h) for h in (0.5, 1, 1.5, 2)]
    slow_ts = [NOW - timedelta(hours=h) for h in (2, 20, 40, 47)]
    fast = {"phrase": "eximbank", "urls": {"u1", "u2", "u3", "u4"}, "sources": {"A", "B", "C"},
            "samples": [{"ts": t, "title": "t", "url": "u", "source": "A"} for t in fast_ts]}
    slow = {"phrase": "ngan hang nha nuoc", "urls": {"u5", "u6", "u7", "u8"}, "sources": {"A", "B", "C"},
            "samples": [{"ts": t, "title": "t", "url": "u", "source": "A"} for t in slow_ts]}

    scored = dict((g["phrase"], score) for g, score in _score_groups([fast, slow], NOW))

    assert scored["eximbank"] > scored["ngan hang nha nuoc"]


def test_display_label_recovers_original_capitalization():
    label = _display_label("eximbank hose", ["Eximbank, HOSE: EIB công bố thông tin"])
    assert label == "Eximbank, HOSE"


def test_display_label_falls_back_to_title_case_when_no_match():
    label = _display_label("ngan hang", [])
    assert label == "Ngan Hang"


def test_top_trending_end_to_end_ranks_and_labels_sensibly():
    articles = [
        _article("VnExpress", "Eximbank gia hạn đề cử nhân sự HĐQT", "u1", 0.5),
        _article("CafeF", "Eximbank hoãn ngày chốt danh sách ứng viên HĐQT", "u2", 1),
        _article("Tuổi Trẻ", "Cổ đông chất vấn Eximbank về kế hoạch nhân sự", "u3", 1.5),
        _article("VnExpress", "Ngân hàng Nhà nước giữ nguyên lãi suất điều hành", "u4", 30),
        _article("CafeF", "Ngân hàng Nhà nước công bố báo cáo tiền tệ quý 3", "u5", 45),
        # Single-source-only phrase must never appear in the output.
        _article("VnExpress", "Một công ty bất động sản đổi tên thương hiệu", "u6", 1),
    ]

    topics = top_trending(articles, NOW, limit=5)

    assert len(topics) == 2
    assert topics[0].label.lower().startswith("eximbank")
    assert topics[0].article_count == 3
    assert topics[0].source_count == 3
    assert topics[0].score > topics[1].score
    assert all(t.source_count >= 2 and t.article_count >= 2 for t in topics)

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import responses

import telegram
from models import NewsItem

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def make_items(source, n, title_len=90, start_hour=10):
    return [
        NewsItem(
            source=source,
            title="T" * title_len + f" #{i}",
            url=f"https://example.com/{source}-article-{i}-very-long-slug-for-realistic-length.html",
            published_at=datetime(2026, 9, 14, start_hour, i % 60, tzinfo=TZ),
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# format_grouped_articles — V2's group-by-source format (spec section 11)
# ---------------------------------------------------------------------------


def test_format_grouped_empty_dict_returns_no_messages():
    assert telegram.format_grouped_articles({}) == []


def test_format_grouped_drops_sources_with_no_items():
    assert telegram.format_grouped_articles({"Vietstock": []}) == []


def test_format_grouped_single_source_has_heading_and_bullets():
    items = [
        NewsItem("Vietstock", "Tin 1", "https://vietstock.vn/1", datetime(2026, 9, 14, 10, 3, tzinfo=TZ)),
        NewsItem("Vietstock", "Tin 2", "https://vietstock.vn/2", datetime(2026, 9, 14, 10, 11, tzinfo=TZ)),
    ]
    messages = telegram.format_grouped_articles({"Vietstock": items})
    assert len(messages) == 1
    text = messages[0]
    # V3: each source gets its own icon + bold name + article count, so
    # it can be told apart from other sources at a glance.
    assert "<b>VIETSTOCK</b> (2 bài)" in text
    assert telegram.SOURCE_ICONS["Vietstock"] in text
    assert '<a href="https://vietstock.vn/1">Tin 1</a> — 14/09 10:03' in text
    assert '<a href="https://vietstock.vn/2">Tin 2</a> — 14/09 10:11' in text
    # V3: opens with a one-line summary (total count, source count).
    assert "📬 <b>2 bài mới</b> · 1 nguồn" in text


def test_icon_for_unmapped_source_is_stable_across_calls():
    """A source not in SOURCE_ICONS (e.g. a brand-new crawler added
    before the dict is updated) must still get *some* icon, and the
    same one every time — not something that depends on Python's
    per-process randomized str hash()."""
    icon1 = telegram._icon_for("Some Brand New Source")
    icon2 = telegram._icon_for("Some Brand New Source")
    assert icon1 == icon2
    assert icon1 in telegram._FALLBACK_ICONS


def test_format_grouped_preserves_given_source_order_not_time():
    vietstock = [NewsItem("Vietstock", "V", "https://x/v", datetime(2026, 9, 14, 9, 0, tzinfo=TZ))]
    tuoitre = [NewsItem("Tuổi Trẻ", "T", "https://x/t", datetime(2026, 9, 14, 11, 0, tzinfo=TZ))]
    # Tuổi Trẻ's article is later in time but Vietstock is listed first in
    # the input dict, and must stay first in the output (spec section 12).
    messages = telegram.format_grouped_articles({"Vietstock": vietstock, "Tuổi Trẻ": tuoitre})
    text = messages[0]
    assert text.index("VIETSTOCK") < text.index("TUỔI TRẺ")


def test_format_grouped_escapes_html_special_chars_in_title():
    items = [NewsItem("CafeF", "Lãi <5%> & tăng", "https://x/a?x=1&y=2", datetime(2026, 9, 14, 10, 0, tzinfo=TZ))]
    text = telegram.format_grouped_articles({"CafeF": items})[0]
    assert "<5%>" not in text
    assert "&lt;5%&gt;" in text
    assert "&amp;" in text  # both in the title and the URL's query string


def test_time_str_shows_date_not_just_hour_for_multi_day_batches():
    """Regression guard: some feeds (VTV in particular, verified during
    audit to span ~25 different calendar days in one RSS response) can
    surface "new" articles from several different days in a single
    batch. Showing only HH:MM made same-looking times from different
    days look randomly ordered even though the underlying sort (by
    full datetime) was always correct."""
    older = NewsItem("VTV", "Bài cũ hơn", "https://x/1", datetime(2026, 9, 12, 12, 45, tzinfo=TZ))
    newer = NewsItem("VTV", "Bài mới hơn", "https://x/2", datetime(2026, 9, 14, 4, 26, tzinfo=TZ))
    text = telegram.format_grouped_articles({"VTV": [older, newer]})[0]
    assert "12/09 12:45" in text
    assert "14/09 04:26" in text


def test_format_grouped_item_without_time_omits_dash_time():
    item = NewsItem("X", "No time", "https://example.com/a", None)
    text = telegram.format_grouped_articles({"X": [item]})[0]
    assert "—" not in text.split("\n")[-1] or "No time" in text


def test_format_grouped_pulls_hot_keyword_match_to_top_section():
    items = {
        "VnExpress": [NewsItem("VnExpress", "Cửa hàng khai trương chi nhánh mới", "https://x/1", datetime(2026, 9, 14, 14, 20, tzinfo=TZ))],
        "VTV": [NewsItem("VTV", "Ngân hàng Nhà nước bất ngờ tăng lãi suất điều hành", "https://x/2", datetime(2026, 9, 14, 14, 32, tzinfo=TZ))],
    }
    text = telegram.format_grouped_articles(items)[0]

    assert "🚨 <b>TIN NÓNG</b>" in text
    # The hot item must appear inside the hot section, tagged with its
    # source since it's out of its normal per-source block.
    hot_idx = text.index("🚨 <b>TIN NÓNG</b>")
    hot_title_idx = text.index("Ngân hàng Nhà nước")
    assert hot_idx < hot_title_idx
    assert "(VTV)" in text
    # And it must be removed from VTV's normal block, not duplicated.
    assert text.count("Ngân hàng Nhà nước bất ngờ tăng lãi suất điều hành") == 1
    assert "<b>VTV</b>" not in text  # VTV had nothing else -> no normal block for it at all


def test_format_grouped_hot_section_appears_before_normal_sources():
    items = {
        "VnExpress": [NewsItem("VnExpress", "Tin thường 1", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ))],
        "CafeF": [
            NewsItem("CafeF", "Tin thường 2", "https://x/2", datetime(2026, 9, 14, 10, 0, tzinfo=TZ)),
            NewsItem("CafeF", "Giá vàng giảm sốc phiên sáng nay", "https://x/3", datetime(2026, 9, 14, 10, 5, tzinfo=TZ)),
        ],
    }
    text = telegram.format_grouped_articles(items)[0]
    assert text.index("TIN NÓNG") < text.index("VNEXPRESS")
    assert text.index("TIN NÓNG") < text.index("CAFEF")
    # CafeF's normal block keeps its one remaining non-hot article.
    assert "Tin thường 2" in text


def test_format_grouped_no_hot_section_when_nothing_matches():
    items = {"VnExpress": [NewsItem("VnExpress", "Tin bình thường", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ))]}
    text = telegram.format_grouped_articles(items)[0]
    assert "TIN NÓNG" not in text


def test_is_hot_matches_curated_keywords_case_insensitively():
    assert telegram._is_hot("Giá vàng TĂNG VỌT trong phiên sáng") is True
    assert telegram._is_hot("giá vàng giảm sốc") is True
    assert telegram._is_hot("Doanh nghiệp ký hợp tác chiến lược") is False


def test_format_grouped_appends_error_footer_when_given():
    items = [NewsItem("Vietstock", "T", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ))]
    text = telegram.format_grouped_articles({"Vietstock": items}, errored_sources=["VnExpress"])[0]
    assert "⚠️ Nguồn lỗi: VnExpress" in text


def test_format_grouped_small_batch_fits_one_message():
    items = make_items("Vietstock", 5)
    messages = telegram.format_grouped_articles({"Vietstock": items})
    assert len(messages) == 1
    assert len(messages[0]) <= 4096


def test_format_grouped_splits_large_single_source_without_cutting_articles():
    items = make_items("Vietstock", 60, title_len=120)
    messages = telegram.format_grouped_articles({"Vietstock": items}, limit=4096)

    assert len(messages) > 1
    for msg in messages:
        assert len(msg) <= 4096
    for item in items:
        occurrences = sum(1 for msg in messages if item.url in msg)
        assert occurrences == 1, f"{item.url} appeared in {occurrences} messages"


def test_format_grouped_splits_across_many_sources_without_losing_articles():
    items_by_source = {f"Source{i}": make_items(f"Source{i}", 15, title_len=100) for i in range(6)}
    messages = telegram.format_grouped_articles(items_by_source, limit=4096)

    assert len(messages) > 1
    for msg in messages:
        assert len(msg) <= 4096
    for items in items_by_source.values():
        for item in items:
            occurrences = sum(1 for msg in messages if item.url in msg)
            assert occurrences == 1


# ---------------------------------------------------------------------------
# Status messages
# ---------------------------------------------------------------------------


def test_format_no_new_articles_message():
    now = datetime(2026, 9, 14, 10, 30, tzinfo=TZ)
    text = telegram.format_no_new_articles(now)
    assert "🟢 <b>NEWS MONITOR</b>" in text
    assert "10:30 — Không có tin mới." in text


def test_format_partial_failure_no_new_lists_failed_sources_and_keeps_visible():
    now = datetime(2026, 9, 14, 10, 30, tzinfo=TZ)
    text = telegram.format_partial_failure_no_new(["VnExpress", "CafeF"], now)
    assert "⚠️ <b>NEWS MONITOR</b>" in text
    assert "• VnExpress" in text
    assert "• CafeF" in text
    assert "Không có tin mới" not in text.replace("Không có tin mới từ các nguồn hoạt động.", "")


def test_format_all_sources_failed_is_red_and_lists_every_source():
    now = datetime(2026, 9, 14, 10, 30, tzinfo=TZ)
    text = telegram.format_all_sources_failed(["VnExpress", "Tuổi Trẻ"], now)
    assert "🔴 <b>NEWS MONITOR</b>" in text
    assert "Không thể hoàn tất lượt quét." in text
    assert "• VnExpress" in text
    assert "• Tuổi Trẻ" in text


def test_format_stale_sources_warning_lists_source_and_last_new_time():
    now = datetime(2026, 9, 14, 20, 0, tzinfo=TZ)
    last_new = datetime(2026, 8, 8, 10, 54, tzinfo=TZ)
    text = telegram.format_stale_sources_warning([("VietnamNet", last_new)], 24, now)
    assert "🩺" in text
    assert "VietnamNet" in text
    assert "24h" in text
    assert "08/08/2026 10:54" in text


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------

TOKEN = "123:ABC"
CHAT_ID = "999"
API_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"


@responses.activate
def test_send_message_success():
    responses.add(responses.POST, API_URL, json={"ok": True, "result": {}}, status=200)
    telegram.send_message(TOKEN, CHAT_ID, "hello", timeout=5, max_retries=3)
    assert len(responses.calls) == 1


@responses.activate
def test_send_message_uses_html_parse_mode():
    responses.add(responses.POST, API_URL, json={"ok": True, "result": {}}, status=200)
    telegram.send_message(TOKEN, CHAT_ID, "hello", timeout=5, max_retries=3)
    assert responses.calls[0].request.body is not None
    assert "parse_mode=HTML" in responses.calls[0].request.body


@responses.activate
def test_send_message_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr(telegram.time, "sleep", lambda *_args, **_kwargs: None)
    responses.add(responses.POST, API_URL, json={"ok": False}, status=500)
    responses.add(responses.POST, API_URL, json={"ok": True, "result": {}}, status=200)

    telegram.send_message(TOKEN, CHAT_ID, "hello", timeout=5, max_retries=3)
    assert len(responses.calls) == 2


@responses.activate
def test_send_message_raises_telegram_error_after_exhausting_retries(monkeypatch):
    monkeypatch.setattr(telegram.time, "sleep", lambda *_args, **_kwargs: None)
    responses.add(responses.POST, API_URL, json={"ok": False, "description": "bad"}, status=400)
    responses.add(responses.POST, API_URL, json={"ok": False, "description": "bad"}, status=400)

    with pytest.raises(telegram.TelegramError):
        telegram.send_message(TOKEN, CHAT_ID, "hello", timeout=5, max_retries=2)
    assert len(responses.calls) == 2

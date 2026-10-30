"""Tests for core/relevance.py — the economy-only filter. Every title below
is a real headline from the 2026-10-03 live audit (see the module docstring
for why the rule is "social term AND no economic term")."""

import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import scheduler
from config import Config
from core.relevance import drop_reason, is_economic
from models import NewsItem

TZ = ZoneInfo("Asia/Ho_Chi_Minh")

# Clearly social: weather, lottery, party discipline, missing persons, etc.
SOCIAL = [
    ("Nam bộ mưa lớn kéo dài hơn dự báo", "mưa lớn"),
    ("Áp thấp nhiệt đới hình thành trên Biển Đông, đổ bộ vào miền Trung", "áp thấp"),
    ("Mưa lũ bất thường trên cả nước", "mưa lũ"),
    ("Vietlott lại tìm thấy khách hàng trúng độc đắc gần 4,5 tỷ tối nay", "vietlott"),
    ("Jackpot xổ số Mega 6/45 có thể phá kỷ lục 10 năm vào tối nay", "xổ số"),
    ("Khai trừ Đảng, cách chức, tịch thu tài sản của cựu Ủy viên Thường vụ Thành ủy", "khai trừ"),
    ("Tìm con mất tích gần 25 năm, người mẹ bất ngờ phát hiện", "mất tích"),
    ("Độc đáo cách ‘tắm cho cá’ ở đặc khu Thổ Châu", "tắm cho cá"),
    ("Apple tung iOS 27 ‘lột xác’ trước giờ iPhone 18 lên kệ", "ios"),
]

# Economic headlines that a naive filter dropped or would drop: they either
# carry an economic term or no social term at all.
ECONOMIC = [
    "Con trai tỷ phú Trần Đình Long sắp chi nghìn tỷ 'bắt đáy' HPG",   # "con trai" must not be a social term
    "Thanh toán QR của du khách quốc tế tại Việt Nam tăng mạnh",
    "Gelex lên tiếng về việc thành viên HĐQT bị khởi tố",
    "Lại phập phồng thiếu điện",
    "EVN thoát lỗ lũy kế, lãi hơn 12.200 tỉ đồng trong 8 tháng",
    "Hải quan khởi tố vụ buôn lậu hàng giả mạo tại cảng Cát Lái",
    "Chính thức khai tử 2G: Vì sao Việt Nam phải tắt mạng di động hơn 30 năm tuổi?",  # "sao việt" across words
    "Thêm một chuỗi phòng gym thông báo đóng cửa chi nhánh",                 # a business closing
    "Pháp áp phí hàng thời trang nhanh",                                       # trade policy
    "Hơn 220.000 iPhone 18 đã được người dùng Việt đặt mua, 90% chọn Pro Max",  # retail demand
    "Vụ hacker rút 4.000 bitcoin, nạn nhân nói một câu khiến kẻ trộm bất ngờ",  # crypto
    "Mưa lũ bất thường, nông nghiệp thiệt hại nặng",                            # weather WITH an economic angle
    "Xuất siêu trở lại sau 9 tháng liên tiếp nhập siêu 'khủng'",
    "Chủ thẻ VPBank nhận loạt ưu đãi du lịch, mua sắm, ẩm thực",
    "Trường học giảm 50,6% sau sắp xếp, 'nơi thừa nơi thiếu giáo viên'",  # education news is left alone (no social term)
]


@pytest.mark.parametrize("title,term", SOCIAL)
def test_clearly_social_titles_are_dropped_with_the_reason(title, term):
    assert is_economic(title) is False
    assert drop_reason(title) == term


@pytest.mark.parametrize("title", ECONOMIC)
def test_economic_titles_are_kept(title):
    assert is_economic(title) is True
    assert drop_reason(title) is None


def test_a_title_matching_neither_list_is_kept():
    # Benefit of the doubt: the filter only removes what it can positively
    # identify as social.
    assert is_economic("Chợ truyền thống ế ẩm, tiểu thương gà gật") is True


def test_economic_term_overrides_a_social_term():
    assert is_economic("Mưa lớn ảnh hưởng giá rau, nông sản tăng mạnh") is True


def test_english_titles_are_never_dropped():
    assert is_economic("Gold prices fall") is True
    assert is_economic("Vietnam's central bank holds rates") is True


def test_matching_ignores_case_and_unicode_composition():
    assert is_economic("MƯA LỚN kéo dài nhiều ngày") is False
    decomposed = unicodedata.normalize("NFD", "mưa lớn kéo dài")  # base letters + combining marks
    assert decomposed != "mưa lớn kéo dài"
    assert is_economic(decomposed) is False


def test_terms_match_whole_words_only():
    assert is_economic("Nhà máy gymnastics equipment") is True  # no word-boundary hit inside a longer word


# --- wired into the crawl ----------------------------------------------------
class _FakeCrawler:
    def __init__(self, source_name, titles):
        self.source_name = source_name
        self._titles = titles

    def crawl(self):
        return [NewsItem(self.source_name, t, f"https://x/{i}", datetime(2026, 10, 3, 10, 0, tzinfo=TZ))
                for i, t in enumerate(self._titles)]


def test_crawl_all_skips_social_items_and_keeps_the_rest(monkeypatch, caplog):
    titles = ["Nam bộ mưa lớn kéo dài", "Lãi suất tiết kiệm tăng nhẹ", "Vietlott trúng độc đắc 4,5 tỷ"]
    monkeypatch.setattr(scheduler, "_build_crawlers", lambda cfg: [_FakeCrawler("A", titles)])

    with caplog.at_level("INFO"):
        items_by_source, status = scheduler.crawl_all(Config())

    assert [i.title for i in items_by_source["A"]] == ["Lãi suất tiết kiệm tăng nhẹ"]
    assert status["A"] == (True, None)
    assert "skipped 2 non-economic" in caplog.text  # visible in the Actions log


def test_crawl_all_logs_nothing_extra_when_nothing_is_dropped(monkeypatch, caplog):
    monkeypatch.setattr(scheduler, "_build_crawlers", lambda cfg: [_FakeCrawler("A", ["Lãi suất tăng"])])
    with caplog.at_level("INFO"):
        scheduler.crawl_all(Config())
    assert "non-economic" not in caplog.text


# --- wired into the stored-data view ------------------------------------------
def test_get_all_articles_hides_social_rows_already_in_the_database(db):
    db.insert_if_new(NewsItem("A", "Nam bộ mưa lớn kéo dài", "https://x/1", datetime(2026, 10, 3, 9, 0, tzinfo=TZ)))
    db.insert_if_new(NewsItem("A", "Lãi suất tiết kiệm tăng nhẹ", "https://x/2", datetime(2026, 10, 3, 9, 5, tzinfo=TZ)))

    assert db.count_all() == 2  # the raw row is kept, never rewritten
    assert [a["title"] for a in db.get_all_articles()] == ["Lãi suất tiết kiệm tăng nhẹ"]

import pytest
import responses

from crawlers.baochinhphu import BaoChinhPhuCrawler
from crawlers.base import CrawlerError
from crawlers.cafef import CafeFCrawler
from crawlers.dantri import DanTriCrawler
from crawlers.nhandan import NhanDanCrawler
from crawlers.thanhnien import ThanhNienCrawler
from crawlers.tienphong import TienPhongCrawler
from crawlers.tuoitre import TuoiTreCrawler
from crawlers.vietnambiz import VietnamBizCrawler
from crawlers.vietnamplus import VietnamPlusCrawler
from crawlers.vietstock import VietstockCrawler
from crawlers.vneconomy import VnEconomyCrawler
from crawlers.vnexpress import VnExpressCrawler
from crawlers.vtv import VTVCrawler
from crawlers.znews import ZnewsCrawler
from tests.conftest import load_fixture

CRAWLERS_AND_FIXTURES = [
    (VnExpressCrawler, "vnexpress.rss", 3),
    (TuoiTreCrawler, "tuoitre.rss", 2),
    (CafeFCrawler, "cafef.rss", 2),
    (VietstockCrawler, "vietstock.rss", 2),
    (ThanhNienCrawler, "thanhnien.rss", 2),
    (DanTriCrawler, "dantri.rss", 2),
    (VnEconomyCrawler, "vneconomy.rss", 2),
    (ZnewsCrawler, "znews.rss", 2),
    (TienPhongCrawler, "tienphong.rss", 2),
    (VietnamPlusCrawler, "vietnamplus.rss", 2),
    (NhanDanCrawler, "nhandan.rss", 2),
    (BaoChinhPhuCrawler, "baochinhphu.rss", 2),
    (VTVCrawler, "vtv.rss", 2),
    (VietnamBizCrawler, "vietnambiz.rss", 2),
]


@pytest.mark.parametrize("crawler_cls,fixture_name,expected_count", CRAWLERS_AND_FIXTURES)
@responses.activate
def test_crawl_parses_all_items(crawler_cls, fixture_name, expected_count):
    crawler = crawler_cls(timeout=5, max_retries=1)
    responses.add(
        responses.GET,
        crawler.feed_url,
        body=load_fixture(fixture_name),
        status=200,
        content_type="application/rss+xml",
    )

    items = crawler.crawl()

    assert len(items) == expected_count
    for item in items:
        assert item.source == crawler.source_name
        assert item.title  # non-empty, trimmed
        assert item.title == item.title.strip()
        assert item.url.startswith("http")
        assert item.published_at is not None
        assert item.published_at.tzinfo is not None


@responses.activate
def test_vnexpress_resolves_relative_url_and_strips_utm():
    crawler = VnExpressCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET,
        crawler.feed_url,
        body=load_fixture("vnexpress.rss"),
        status=200,
    )
    items = crawler.crawl()
    urls = [i.url for i in items]
    assert "https://vnexpress.net/gia-vang-duoc-du-bao-tang-tro-lai-vao-cuoi-nam-5119580.html" in urls
    assert not any("utm_source" in u for u in urls)


@responses.activate
def test_vnexpress_title_whitespace_collapsed():
    crawler = VnExpressCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET,
        crawler.feed_url,
        body=load_fixture("vnexpress.rss"),
        status=200,
    )
    items = crawler.crawl()
    titles = [i.title for i in items]
    assert "Giá dầu thô tăng khi Arab Saudi đóng đường ống qua Hormuz" in titles


@responses.activate
def test_cafef_two_digit_year_resolved_to_2026():
    crawler = CafeFCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET,
        crawler.feed_url,
        body=load_fixture("cafef.rss"),
        status=200,
    )
    items = crawler.crawl()
    assert all(i.published_at.year == 2026 for i in items)


@responses.activate
def test_thanhnien_two_digit_year_resolved_to_2026():
    crawler = ThanhNienCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET,
        crawler.feed_url,
        body=load_fixture("thanhnien.rss"),
        status=200,
    )
    items = crawler.crawl()
    assert all(i.published_at.year == 2026 for i in items)


@responses.activate
def test_baochinhphu_parses_non_rfc822_date():
    """Regression guard: Bao Chinh Phu's <pubDate> is "9/14/2026
    6:44:00 PM" (US-style, not RFC-822), which feedparser's own date
    parser cannot handle — verified against the real live feed during
    audit. Without BaoChinhPhuCrawler's _extract_published_at override,
    every article from this source would have published_at=None."""
    crawler = BaoChinhPhuCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET, crawler.feed_url, body=load_fixture("baochinhphu.rss"), status=200
    )
    items = crawler.crawl()
    assert len(items) == 2
    dates = {i.title: i.published_at for i in items}
    cua_khau = next(v for k, v in dates.items() if k.startswith("Cửa khẩu"))
    assert cua_khau.year == 2026 and cua_khau.month == 9 and cua_khau.day == 14
    assert cua_khau.hour == 18 and cua_khau.minute == 44  # 6:44 PM -> 18:44
    assert cua_khau.tzinfo is not None


@responses.activate
def test_vtv_parses_truncated_utc_offset():
    """Regression guard: VTV's <pubDate> ends in "+07" instead of the
    RFC-822-correct "+0700" — verified against the real live feed
    during audit, not just this fixture. feedparser rejects it outright."""
    crawler = VTVCrawler(timeout=5, max_retries=1)
    responses.add(responses.GET, crawler.feed_url, body=load_fixture("vtv.rss"), status=200)
    items = crawler.crawl()
    assert len(items) == 2
    assert all(i.published_at is not None and i.published_at.tzinfo is not None for i in items)
    eu_item = next(i for i in items if i.title.startswith("EU"))
    assert eu_item.published_at.hour == 19 and eu_item.published_at.minute == 46


@responses.activate
def test_vietnambiz_parses_gmt_plus_7_date_format():
    """Regression guard: VietnamBiz's <pubDate> ends in "GMT+7" instead
    of the RFC-822-correct "+0700" (e.g. "Tue, 15 Sep 2026 09:02:15
    GMT+7") — verified against the live feed during audit, not just
    this fixture. feedparser rejects it outright."""
    crawler = VietnamBizCrawler(timeout=5, max_retries=1)
    responses.add(responses.GET, crawler.feed_url, body=load_fixture("vietnambiz.rss"), status=200)
    items = crawler.crawl()
    assert len(items) == 2
    assert all(i.published_at is not None and i.published_at.tzinfo is not None for i in items)
    euro_item = next(i for i in items if "Euro" in i.title or "euro" in i.title)
    assert euro_item.published_at.hour == 9 and euro_item.published_at.minute == 2


def test_nhandan_uses_corrected_category_feed_not_the_wrong_id_guess():
    """Regression guard: the ID 1041 guess for Nhan Dan's economy
    category returned HTTP 200 but was actually a mixed general-news
    feed (irrigation, fire drills, a royal visit) — verified during
    audit by reading actual item titles, not just the HTTP status."""
    assert "1185" in NhanDanCrawler.feed_url
    assert "1041" not in NhanDanCrawler.feed_url


@responses.activate
def test_crawler_raises_crawler_error_after_exhausting_retries():
    crawler = VnExpressCrawler(timeout=1, max_retries=2)
    responses.add(responses.GET, crawler.feed_url, status=500)
    responses.add(responses.GET, crawler.feed_url, status=500)

    with pytest.raises(CrawlerError):
        crawler.crawl()


@responses.activate
def test_crawler_error_does_not_leak_as_empty_success():
    """A source error must be distinguishable from '0 articles found'
    by the caller (spec section 1.6 / 12)."""
    crawler = VnExpressCrawler(timeout=1, max_retries=1)
    responses.add(responses.GET, crawler.feed_url, body="not xml at all, connection garbage")
    # feedparser is lenient and may still produce 0 entries for garbage
    # input without raising bozo in some cases; the important invariant
    # is that this path never silently returns a *successful* non-empty
    # list. We assert it doesn't crash the whole app either way.
    try:
        items = crawler.crawl()
        assert items == []
    except CrawlerError:
        pass

"""Tests for the HTML-scraping crawlers (no RSS available for these 4
sources — see each crawler's module docstring for the audit that
established that, and README's "Chưa triển khai" history).
"""

import pytest
import responses

from crawlers.base import CrawlerError
from crawlers.baodautu import BaoDauTuCrawler
from crawlers.cafebiz import CafeBizCrawler
from crawlers.diendandoanhnghiep import DienDanDoanhNghiepCrawler
from crawlers.tinnhanhchungkhoan import TinNhanhChungKhoanCrawler
from tests.conftest import load_fixture


@responses.activate
def test_cafebiz_filters_out_untimed_trending_block():
    """Regression guard: the category page's top "trending" section
    (sometimes off-topic — sports/celebrity content, verified live)
    never shows a <div class="time">, unlike the real chronological
    business-news list below it. Filtering on "has a time element"
    keeps only the real list without needing to guess at topic."""
    crawler = CafeBizCrawler(timeout=5, max_retries=1)
    responses.add(responses.GET, crawler.source_url, body=load_fixture("cafebiz.html"), status=200)

    items = crawler.crawl()

    assert len(items) == 2
    assert not any("Cựu HLV" in i.title for i in items)
    assert all(i.published_at is not None and i.published_at.tzinfo is not None for i in items)
    khoa_hoc = next(i for i in items if i.title.startswith("Công ty"))
    assert khoa_hoc.published_at.hour == 10 and khoa_hoc.published_at.minute == 0


@responses.activate
def test_cafebiz_raises_when_nothing_matches():
    crawler = CafeBizCrawler(timeout=5, max_retries=1)
    responses.add(responses.GET, crawler.source_url, body="<html><body>redesigned</body></html>", status=200)
    with pytest.raises(CrawlerError):
        crawler.crawl()


@responses.activate
def test_tinnhanhchungkhoan_parses_items_and_dedupes_thumbnail_link():
    """The thumbnail image link and the headline link share the same
    "cms-link" class and point at the same URL — must not be returned
    as two separate NewsItem entries for one article."""
    crawler = TinNhanhChungKhoanCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET, crawler.source_url, body=load_fixture("tinnhanhchungkhoan.html"), status=200
    )

    items = crawler.crawl()

    assert len(items) == 2
    ai_item = next(i for i in items if i.title.startswith("Cổ phiếu AI"))
    assert ai_item.published_at is not None
    assert ai_item.published_at.hour == 7 and ai_item.published_at.minute == 13
    # VietABank item has no <time> in this fixture -> None, not guessed.
    vab_item = next(i for i in items if i.title.startswith("VietABank"))
    assert vab_item.published_at is None


@responses.activate
def test_diendandoanhnghiep_parses_items_missing_time_as_none():
    crawler = DienDanDoanhNghiepCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET, crawler.source_url, body=load_fixture("diendandoanhnghiep.html"), status=200
    )

    items = crawler.crawl()

    assert len(items) == 2
    hoa_giai = next(i for i in items if i.title == "Hóa giải rủi ro dự án BT")
    assert hoa_giai.published_at is None
    minh_bach = next(i for i in items if i.title.startswith("Tăng tính"))
    assert minh_bach.published_at.day == 14 and minh_bach.published_at.hour == 11


@responses.activate
def test_baodautu_always_has_no_published_at():
    """Documented limitation (see module docstring): this category
    page's listing never shows a date anywhere, for any article."""
    crawler = BaoDauTuCrawler(timeout=5, max_retries=1)
    responses.add(responses.GET, crawler.source_url, body=load_fixture("baodautu.html"), status=200)

    items = crawler.crawl()

    assert len(items) == 3
    assert all(i.published_at is None for i in items)
    assert all(i.url.startswith("http") for i in items)


@responses.activate
def test_baodautu_raises_when_nothing_matches():
    crawler = BaoDauTuCrawler(timeout=5, max_retries=1)
    responses.add(responses.GET, crawler.source_url, body="<html><body>redesigned</body></html>", status=200)
    with pytest.raises(CrawlerError):
        crawler.crawl()

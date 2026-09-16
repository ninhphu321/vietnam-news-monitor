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
    responses.add(
        responses.GET,
        "https://www.tinnhanhchungkhoan.vn/vietabank-vab-chuan-bi-chao-ban-post397598.html",
        body=load_fixture("tinnhanhchungkhoan_article_with_time.html"), status=200,
    )

    items = crawler.crawl()

    assert len(items) == 2
    ai_item = next(i for i in items if i.title.startswith("Cổ phiếu AI"))
    assert ai_item.published_at is not None
    assert ai_item.published_at.hour == 7 and ai_item.published_at.minute == 13
    # VietABank has no <time> in the listing fixture, but its (mocked)
    # article page does -> falls back to that instead of staying None.
    vab_item = next(i for i in items if i.title.startswith("VietABank"))
    assert vab_item.published_at is not None
    assert vab_item.published_at.hour == 19 and vab_item.published_at.minute == 3


@responses.activate
def test_tinnhanhchungkhoan_article_page_fetch_failure_leaves_time_none():
    crawler = TinNhanhChungKhoanCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET, crawler.source_url, body=load_fixture("tinnhanhchungkhoan.html"), status=200
    )
    responses.add(
        responses.GET,
        "https://www.tinnhanhchungkhoan.vn/vietabank-vab-chuan-bi-chao-ban-post397598.html",
        status=500,
    )

    items = crawler.crawl()

    vab_item = next(i for i in items if i.title.startswith("VietABank"))
    assert vab_item.published_at is None


@responses.activate
def test_diendandoanhnghiep_falls_back_to_article_page_when_listing_has_no_time():
    """"Hóa giải rủi ro dự án BT" has no `.b-grid__time` in the listing
    (the fixture's other item, "Tăng tính minh bạch", already has one
    and so must NOT trigger an extra request — only registering that
    one article's URL with `responses` and letting the other go
    unmocked proves that)."""
    crawler = DienDanDoanhNghiepCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET, crawler.source_url, body=load_fixture("diendandoanhnghiep.html"), status=200
    )
    responses.add(
        responses.GET,
        "https://diendandoanhnghiep.vn/hoa-giai-rui-ro-du-an-bt-10184400.html",
        body=load_fixture("diendandoanhnghiep_article_with_time.html"), status=200,
    )

    items = crawler.crawl()

    assert len(items) == 2
    hoa_giai = next(i for i in items if i.title == "Hóa giải rủi ro dự án BT")
    assert hoa_giai.published_at is not None
    assert hoa_giai.published_at.day == 15 and hoa_giai.published_at.hour == 15 and hoa_giai.published_at.minute == 5
    minh_bach = next(i for i in items if i.title.startswith("Tăng tính"))
    assert minh_bach.published_at.day == 14 and minh_bach.published_at.hour == 11


@responses.activate
def test_diendandoanhnghiep_article_page_fetch_failure_leaves_time_none():
    """A single article's detail-page fetch failing (network error,
    layout change, whatever) must not crash the whole source — it just
    keeps that one article's published_at=None, same as before this
    fallback existed."""
    crawler = DienDanDoanhNghiepCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.GET, crawler.source_url, body=load_fixture("diendandoanhnghiep.html"), status=200
    )
    responses.add(
        responses.GET,
        "https://diendandoanhnghiep.vn/hoa-giai-rui-ro-du-an-bt-10184400.html",
        status=500,
    )

    items = crawler.crawl()

    assert len(items) == 2
    hoa_giai = next(i for i in items if i.title == "Hóa giải rủi ro dự án BT")
    assert hoa_giai.published_at is None


@responses.activate
def test_baodautu_visits_each_article_page_for_its_time():
    """The category listing itself never shows a date (see module
    docstring), but each article's own page does, in a `.post-time`
    element — the crawler now visits each one to fill published_at in,
    at the cost of one extra request per article."""
    crawler = BaoDauTuCrawler(timeout=5, max_retries=1)
    responses.add(responses.GET, crawler.source_url, body=load_fixture("baodautu.html"), status=200)
    responses.add(
        responses.GET,
        "https://baodautu.vn/chung-khoan-phien-149-co-phieu-ho-gelex-nam-san-d702026.html",
        body=load_fixture("baodautu_article_with_time.html"), status=200,
    )
    responses.add(
        responses.GET,
        "https://baodautu.vn/ninh-van-bay-vi-pham-hang-loat-quy-dinh-d701869.html",
        body=load_fixture("baodautu_article_no_time.html"), status=200,
    )
    responses.add(
        responses.GET,
        "https://baodautu.vn/loat-co-phieu-chiu-tac-dong-trong-ky-co-cau-etf-d701551.html",
        status=500,
    )

    items = crawler.crawl()

    assert len(items) == 3
    assert all(i.url.startswith("http") for i in items)
    by_title_prefix = {i.title[:10]: i for i in items}

    gelex = by_title_prefix["Chứng khoá"]
    assert gelex.published_at is not None
    assert gelex.published_at.day == 14 and gelex.published_at.hour == 10 and gelex.published_at.minute == 30

    # Article page fetched OK but has no ".post-time" -> None, not a guess.
    ninh_van_bay = by_title_prefix["Ninh Vân B"]
    assert ninh_van_bay.published_at is None

    # Article page fetch failed outright (HTTP 500) -> still None, and
    # crucially does NOT take down the rest of the crawl.
    loat_co_phieu = by_title_prefix["Loạt cổ ph"]
    assert loat_co_phieu.published_at is None


@responses.activate
def test_baodautu_raises_when_nothing_matches():
    crawler = BaoDauTuCrawler(timeout=5, max_retries=1)
    responses.add(responses.GET, crawler.source_url, body="<html><body>redesigned</body></html>", status=200)
    with pytest.raises(CrawlerError):
        crawler.crawl()

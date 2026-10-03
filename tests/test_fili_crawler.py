"""Tests for the FiLi crawler (crawlers/fili.py) — HTML scraping.

The site used to be an AngularJS SPA fed by a POST JSON endpoint; a live
audit on 2026-10-03 found that endpoint dead (405) and the category page
now server-rendered, so the crawler was rewritten (see its docstring).
The fixture is real markup from that audit, trimmed to 3 articles: two
with relative times ("N giờ trước") and one with an absolute time.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest
import responses
from freezegun import freeze_time

from crawlers.base import CrawlerError
from crawlers.fili import FiliCrawler
from tests.conftest import load_fixture

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
URL = "https://fili.vn/ngan-hang-bao-hiem.htm"


def _page():
    return load_fixture("fili_page.html")


@responses.activate
@freeze_time("2026-10-03 12:00:00+00:00")
def test_fili_parses_titles_urls_and_both_time_formats():
    responses.add(responses.GET, URL, body=_page(), status=200)
    items = FiliCrawler(timeout=5, max_retries=1).crawl()

    assert len(items) == 3
    for item in items:
        assert item.source == "FiLi"
        assert item.url.startswith("https://fili.vn/2026/10/")
        assert item.published_at is not None and item.published_at.tzinfo is not None

    first = items[0]
    assert first.title.startswith("Tập trung tín dụng")
    # "4 giờ trước" resolved against the (frozen) crawl moment: 12:00 UTC = 19:00 ICT.
    assert first.published_at == datetime(2026, 10, 3, 15, 0, tzinfo=TZ)
    # Absolute form "02/10/2026 20:58" is read as Vietnam local time.
    absolute = next(i for i in items if i.title.startswith("CEO Jens Lottner"))
    assert absolute.published_at == datetime(2026, 10, 2, 20, 58, tzinfo=TZ)


@responses.activate
def test_fili_decodes_html_entities_in_titles():
    responses.add(responses.GET, URL, body=_page(), status=200)
    titles = [i.title for i in FiliCrawler(timeout=5, max_retries=1).crawl()]
    assert any('"giải ngân nhanh"' in t for t in titles)  # &quot; in the markup
    assert all("&" not in t for t in titles)


@responses.activate
def test_fili_leaves_unparseable_times_as_none():
    html = ('<article class="search-card-item"><h3 class="search-card-title">'
            '<a href="/2026/10/x-1.htm">Tin không rõ giờ</a></h3><time>vừa xong</time></article>')
    responses.add(responses.GET, URL, body=html, status=200)
    [item] = FiliCrawler(timeout=5, max_retries=1).crawl()
    assert item.published_at is None


@responses.activate
def test_fili_dedupes_a_url_listed_twice():
    card = ('<article class="search-card-item"><h3 class="search-card-title">'
            '<a href="/2026/10/x-1.htm">Tin lặp</a></h3><time>1 giờ trước</time></article>')
    responses.add(responses.GET, URL, body=card * 2, status=200)
    assert len(FiliCrawler(timeout=5, max_retries=1).crawl()) == 1


@responses.activate
def test_fili_raises_when_no_articles_are_found():
    """Same loud failure the other HTML crawlers give when a redesign
    changes the markup — never a silent "0 new articles"."""
    responses.add(responses.GET, URL, body="<html><body><p>đã đổi giao diện</p></body></html>", status=200)
    with pytest.raises(CrawlerError):
        FiliCrawler(timeout=5, max_retries=1).crawl()


@responses.activate
def test_fili_raises_after_exhausting_retries_on_http_error():
    responses.add(responses.GET, URL, status=500)
    responses.add(responses.GET, URL, status=500)
    with pytest.raises(CrawlerError):
        FiliCrawler(timeout=1, max_retries=2).crawl()

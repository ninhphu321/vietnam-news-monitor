"""Tests for the FiLi crawler (crawlers/fili.py) — a JSON API, not
RSS or HTML scraping (see module docstring for the audit: the category
page is an AngularJS SPA, so the real data comes from a POST endpoint
found by inspecting the site's own network requests).
"""

import json

import pytest
import responses

from crawlers.base import CrawlerError
from crawlers.fili import FiliCrawler
from tests.conftest import load_fixture


def _fixture_json():
    return json.loads(load_fixture("fili_articles.json"))


@responses.activate
def test_fili_parses_items_and_dotnet_dates():
    crawler = FiliCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.POST, "https://fili.vn/_Partials/ListPageArticle",
        json=_fixture_json(), status=200,
    )

    items = crawler.crawl()

    assert len(items) == 2
    for item in items:
        assert item.source == "FiLi"
        assert item.url.startswith("https://fili.vn/")
        assert item.published_at is not None
        assert item.published_at.tzinfo is not None

    eximbank = next(i for i in items if i.title.startswith("Trước thềm"))
    assert eximbank.published_at.hour == 18 and eximbank.published_at.minute == 31


@responses.activate
def test_fili_sends_the_correct_channel_ids_and_url():
    """Regression guard: sending just the category's own ID (734)
    instead of ",734,757,3113,758," (734 plus its sub-categories)
    matches nothing server-side — verified against the live site by
    capturing its own request. A wrong channelid must be caught here,
    not rediscovered by silent "0 articles" in production."""
    crawler = FiliCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.POST, "https://fili.vn/_Partials/ListPageArticle",
        json=_fixture_json(), status=200,
    )

    crawler.crawl()

    assert len(responses.calls) == 1
    sent_body = json.loads(responses.calls[0].request.body)
    assert sent_body["channelid"] == ",734,757,3113,758,"


@responses.activate
def test_fili_raises_when_response_has_no_articles_key():
    crawler = FiliCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.POST, "https://fili.vn/_Partials/ListPageArticle",
        json={"unexpected": "shape"}, status=200,
    )
    with pytest.raises(CrawlerError):
        crawler.crawl()


@responses.activate
def test_fili_raises_when_articles_list_is_empty():
    """The exact failure mode hit during audit when channelid was
    wrong: HTTP 200, well-formed JSON, but zero articles."""
    crawler = FiliCrawler(timeout=5, max_retries=1)
    responses.add(
        responses.POST, "https://fili.vn/_Partials/ListPageArticle",
        json={"LsArticles": [], "Totalrow": 0}, status=200,
    )
    with pytest.raises(CrawlerError):
        crawler.crawl()


@responses.activate
def test_fili_raises_after_exhausting_retries_on_http_error():
    crawler = FiliCrawler(timeout=1, max_retries=2)
    responses.add(responses.POST, "https://fili.vn/_Partials/ListPageArticle", status=500)
    responses.add(responses.POST, "https://fili.vn/_Partials/ListPageArticle", status=500)
    with pytest.raises(CrawlerError):
        crawler.crawl()

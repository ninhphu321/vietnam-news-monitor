"""Báo Đầu tư (baodautu.vn) crawler — HTML scraping (no RSS available).

Audit (2026-09-15): every guessed RSS URL for this site (including its
own declared category IDs) returns HTTP 200 but with a permanently
empty channel (<title>Trang chủ</title>, 0 <item> — verified across
multiple different category slugs, always the same empty shell), so
its RSS system appears to be effectively dead despite not erroring.
Scrapes the "Đầu tư tài chính" category page (id d6) directly instead.

Real limitation: this category page's article cards (all sizes: the
big hero, secondary cards, and the small side list) never show a
publish date anywhere in the listing HTML — only the article's own
page would have it, and fetching every article individually just for
a timestamp is a disproportionate amount of extra traffic for one
source. published_at is therefore always None here, per spec section
16's explicit fallback for a source with no reliable published_at
("có thể dùng first_seen_at nhưng phải ghi rõ đây là fallback") — the
lack of a date is logged so it's clearly a known limitation, not a bug.
"""

import logging
from typing import List

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, CrawlerError
from models import NewsItem
from utils import normalize_title, normalize_url

logger = logging.getLogger(__name__)


class BaoDauTuCrawler(BaseCrawler):
    source_name = "Báo Đầu tư"
    source_url = "https://baodautu.vn/dau-tu-tai-chinh-d6/"

    _TITLE_SELECTOR = "a.fs32, a.fs22, a.fs18, a.title_thumb_square"

    def crawl(self) -> List[NewsItem]:
        raw = self._fetch(self.source_url)
        try:
            soup = BeautifulSoup(raw, "html.parser")
        except Exception as exc:  # noqa: BLE001 - a parser bug must not crash the app
            raise CrawlerError(f"{self.source_name}: failed to parse HTML: {exc}") from None

        items_by_url = {}
        for link in soup.select(self._TITLE_SELECTOR):
            title = normalize_title(link.get_text())
            href = link.get("href")
            if not title or not href:
                continue
            url = normalize_url(href, base_url=self.source_url)
            items_by_url.setdefault(
                url,
                NewsItem(source=self.source_name, title=title, url=url, published_at=None),
            )

        if not items_by_url:
            raise CrawlerError(
                f"{self.source_name}: no articles found — page structure may have changed"
            )

        logger.debug(
            "%s: %d articles found, none have a published_at (see module docstring).",
            self.source_name, len(items_by_url),
        )
        return list(items_by_url.values())

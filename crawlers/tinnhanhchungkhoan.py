"""Đầu tư Chứng khoán (tinnhanhchungkhoan.vn) crawler — HTML scraping.

Audit (2026-09-15): no RSS found for this source at any of the
standard patterns (`/rss/*.rss` all redirect to a 404 page, no
`<link rel="alternate">` declared anywhere) — see README "Chưa triển
khai" history. Scrapes the Chứng khoán category page directly.

Real quirk: <time datetime="..."> uses a timezone offset without a
colon (e.g. "2026-09-15T07:13:33+0700"). Python's
datetime.fromisoformat() rejects that exact format on Python < 3.11
(it requires "+07:00"); strptime with %z handles both forms, so that
is used instead.

Audit (2026-09-16): a handful of listing items have no <time> in their
`.story` container (verified live: "Công trình Giao thông Đồng Nai
(DGT)..." was one such case). Their own article page has the same
`<time datetime="...">` element, so those items now fall back to one
extra request rather than staying published_at=None.
"""

from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, CrawlerError
from models import NewsItem
from utils import normalize_title, normalize_url


class TinNhanhChungKhoanCrawler(BaseCrawler):
    source_name = "Đầu tư Chứng khoán"
    source_url = "https://www.tinnhanhchungkhoan.vn/chung-khoan/"

    def crawl(self) -> List[NewsItem]:
        raw = self._fetch(self.source_url)
        try:
            soup = BeautifulSoup(raw, "html.parser")
        except Exception as exc:  # noqa: BLE001 - a parser bug must not crash the app
            raise CrawlerError(f"{self.source_name}: failed to parse HTML: {exc}") from None

        items_by_url = {}
        # Both the headline link and its thumbnail image link share the
        # "cms-link" class — selecting only the one inside
        # story__heading avoids matching the thumbnail link too.
        #
        # The same article can also appear multiple times on one page
        # (main chronological list + "related"/"most read" widgets
        # elsewhere), each with a different or missing <time> — verified
        # live: one article appeared 4 times with 3 different
        # timestamps plus one blank. The first occurrence in document
        # order is the main list (correct, freshest); setdefault keeps
        # it and ignores the later, less reliable duplicates.
        for link in soup.select("h2.story__heading a.cms-link, h3.story__heading a.cms-link"):
            title = normalize_title(link.get("title") or link.get_text())
            href = link.get("href")
            if not title or not href:
                continue

            container = link.find_parent(class_="story")
            time_el = container.select_one("time") if container else None
            published_at = self._parse_time(time_el.get("datetime")) if time_el else None

            url = normalize_url(href, base_url=self.source_url)
            items_by_url.setdefault(
                url,
                NewsItem(source=self.source_name, title=title, url=url, published_at=published_at),
            )

        if not items_by_url:
            raise CrawlerError(
                f"{self.source_name}: no articles found — page structure may have changed"
            )

        items = list(items_by_url.values())
        for item in items:
            if item.published_at is None:
                item.published_at = self._fetch_published_at(item.url)
        return items

    def _parse_time(self, raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            dt = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S%z")
        except ValueError:
            return None
        return dt.astimezone(self.tz)

    def _fetch_published_at(self, article_url: str) -> Optional[datetime]:
        """Fallback for listing items with no <time> in their `.story`
        container: visit the article's own page for the same kind of
        <time datetime="..."> element. Best-effort — any failure just
        leaves this one article's time as None, never raises."""
        try:
            raw = self._fetch(article_url)
        except CrawlerError:
            return None
        try:
            soup = BeautifulSoup(raw, "html.parser")
        except Exception:  # noqa: BLE001 - a parser bug must not crash the app
            return None

        time_el = soup.select_one("time")
        if time_el is None:
            return None
        return self._parse_time(time_el.get("datetime"))

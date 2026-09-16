"""Diễn đàn Doanh nghiệp crawler — HTML scraping (no RSS available).

Audit (2026-09-15): no RSS found for the Kinh tế category
(`/chinh-tri-xa-hoi/kinh-te`) at any standard pattern, and the page
declares no `<link rel="alternate">`. Scrapes the category page
directly. Dates are shown as "dd/mm/yyyy HH:MM" text (not an ISO
attribute like the other two HTML-scraped sources), parsed directly.
A few items (mainly the top featured card) have no time element in
the listing at all.

Audit (2026-09-16): for those "no time in listing" items, the
article's own page does have one, in
`<meta name="article:published_time" content="9/16/2026 5:25:01 AM">`
(note: `name=`, not `property=`, despite looking like an OpenGraph-style
tag) (US month/day/year, 12-hour clock — same quirk as Chính phủ/Tuổi
Trẻ's feeds). So instead of leaving those permanently published_at=None,
this crawler now falls back to fetching just that subset of articles'
pages — the majority that already have a listing time are unaffected
(no extra request for them).
"""

from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, CrawlerError
from models import NewsItem
from utils import normalize_title, normalize_url


class DienDanDoanhNghiepCrawler(BaseCrawler):
    source_name = "Diễn đàn Doanh nghiệp"
    source_url = "https://diendandoanhnghiep.vn/chinh-tri-xa-hoi/kinh-te"

    def crawl(self) -> List[NewsItem]:
        raw = self._fetch(self.source_url)
        try:
            soup = BeautifulSoup(raw, "html.parser")
        except Exception as exc:  # noqa: BLE001 - a parser bug must not crash the app
            raise CrawlerError(f"{self.source_name}: failed to parse HTML: {exc}") from None

        items_by_url = {}
        for link in soup.select("h2.b-grid__title a, h3.b-grid__title a"):
            title = normalize_title(link.get_text())
            href = link.get("href")
            if not title or not href:
                continue

            container = link.find_parent(class_="b-grid__row") or link.find_parent(class_="b-grid")
            time_el = container.select_one(".b-grid__time") if container else None
            published_at = self._parse_time(time_el.get_text(strip=True)) if time_el else None

            # First occurrence in document order (main list) wins over
            # any later relisting of the same article elsewhere on the
            # page — same reasoning as the other HTML-scraped crawlers.
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
            naive = datetime.strptime(raw, "%d/%m/%Y %H:%M")
        except ValueError:
            return None
        return naive.replace(tzinfo=self.tz)

    def _fetch_published_at(self, article_url: str) -> Optional[datetime]:
        """Fallback for listing items with no `.b-grid__time`: visit the
        article's own page for its `article:published_time` meta tag.
        Best-effort — any failure (network, missing tag, unparseable
        text) just leaves this one article's time as None, never raises
        (a single flaky article page must not take down the source)."""
        try:
            raw = self._fetch(article_url)
        except CrawlerError:
            return None
        try:
            soup = BeautifulSoup(raw, "html.parser")
        except Exception:  # noqa: BLE001 - a parser bug must not crash the app
            return None

        meta = soup.find("meta", attrs={"name": "article:published_time"})
        if meta is None or not meta.get("content"):
            return None
        try:
            naive = datetime.strptime(meta["content"].strip(), "%m/%d/%Y %I:%M:%S %p")
        except ValueError:
            return None
        return naive.replace(tzinfo=self.tz)

"""Diễn đàn Doanh nghiệp crawler — HTML scraping (no RSS available).

Audit (2026-09-15): no RSS found for the Kinh tế category
(`/chinh-tri-xa-hoi/kinh-te`) at any standard pattern, and the page
declares no `<link rel="alternate">`. Scrapes the category page
directly. Dates are shown as "dd/mm/yyyy HH:MM" text (not an ISO
attribute like the other two HTML-scraped sources), parsed directly.
A few items (mainly the top featured card) have no time element at
all — left as published_at=None per spec section 16's fallback,
rather than guessed.
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
        return list(items_by_url.values())

    def _parse_time(self, raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            naive = datetime.strptime(raw, "%d/%m/%Y %H:%M")
        except ValueError:
            return None
        return naive.replace(tzinfo=self.tz)

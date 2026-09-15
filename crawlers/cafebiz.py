"""CafeBiz crawler — HTML scraping (no RSS available).

Audit (2026-09-15): CafeBiz has no RSS for its "Kinh doanh" category
(`/cau-chuyen-kinh-doanh.chn`) — `/rss/home.rss` exists but is a
site-wide feed mixing weather, tech, and entertainment; no
`/cau-chuyen-kinh-doanh.rss` equivalent to CafeF's pattern despite
being the same corp (VCCorp). So this scrapes the category page
directly with BeautifulSoup.

Real quirk found during audit: the category page itself mixes two
sections — a "trending" block of highlight cards at the top (which
sometimes includes off-topic content like sports/celebrity news and
never shows a timestamp), followed by the actual chronological
business news list (which does). Filtering to "has a <div class="time">
near the title link" reliably keeps only the second section — cheaper
and more robust than trying to detect topic from text.
"""

from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, CrawlerError
from models import NewsItem
from utils import normalize_title, normalize_url


class CafeBizCrawler(BaseCrawler):
    source_name = "CafeBiz"
    source_url = "https://cafebiz.vn/cau-chuyen-kinh-doanh.chn"

    def crawl(self) -> List[NewsItem]:
        raw = self._fetch(self.source_url)
        try:
            soup = BeautifulSoup(raw, "html.parser")
        except Exception as exc:  # noqa: BLE001 - a parser bug must not crash the app
            raise CrawlerError(f"{self.source_name}: failed to parse HTML: {exc}") from None

        items_by_url = {}
        for link in soup.select("a.cfbiznews_title"):
            title = normalize_title(link.get("title") or link.get_text())
            href = link.get("href")
            if not title or not href:
                continue

            time_el = self._find_time_el(link)
            if time_el is None:
                # No timestamp -> this is the untimed "trending" block,
                # not the actual chronological news list (see audit note).
                continue
            published_at = self._parse_time(time_el.get("title"))
            if published_at is None:
                continue

            # A repeated widget elsewhere on the page could relist the
            # same article; keep the first (main list) occurrence, same
            # reasoning as tinnhanhchungkhoan.py's crawler.
            url = normalize_url(href, base_url=self.source_url)
            items_by_url.setdefault(
                url,
                NewsItem(source=self.source_name, title=title, url=url, published_at=published_at),
            )

        if not items_by_url:
            # HTML scraping has no schema to validate against like RSS
            # does — zero matches almost always means the site changed
            # its markup and the selectors above no longer apply, not
            # that there are genuinely no articles.
            raise CrawlerError(
                f"{self.source_name}: no timestamped articles found — page structure may have changed"
            )
        return list(items_by_url.values())

    @staticmethod
    def _find_time_el(link):
        """Look for a nearby ".time" element: verified live, the
        headline link's grandparent (link -> h3 -> card wrapper) is
        the shared container that also holds the time div as a
        sibling of the h3. Deliberately capped at 2 levels rather than
        climbing further — a wider search re-scans each ancestor's
        *entire* subtree, and going up far enough eventually reaches a
        shared container spanning multiple unrelated cards, silently
        borrowing a different article's timestamp (caught by a test
        using a flatter fixture than the real page's actual nesting)."""
        node = link
        for _ in range(2):
            node = node.parent
            if node is None:
                return None
            time_el = node.select_one(".time")
            if time_el is not None:
                return time_el
        return None
        return None

    def _parse_time(self, raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        try:
            naive = datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
            return None
        return naive.replace(tzinfo=self.tz)

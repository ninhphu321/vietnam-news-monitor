"""Báo Đầu tư (baodautu.vn) crawler — HTML scraping (no RSS available).

Audit (2026-09-15): every guessed RSS URL for this site (including its
own declared category IDs) returns HTTP 200 but with a permanently
empty channel (<title>Trang chủ</title>, 0 <item> — verified across
multiple different category slugs, always the same empty shell), so
its RSS system appears to be effectively dead despite not erroring.
Scrapes the "Đầu tư tài chính" category page (id d6) directly instead.

Audit (2026-09-16): the category listing itself (all card sizes) still
never shows a publish date, but every article's own page does, in a
consistent `<span class="post-time">- dd/mm/yyyy HH:MM</span>` — so
published_at is now filled in with one extra request per article
rather than left None. This does mean a full crawl costs ~N+1 requests
instead of 1 (N = articles on the category page), which is the
"disproportionate extra traffic" this crawler originally avoided —
accepted per user request, since a missing timestamp here was worse
than the added traffic. A single article's detail page failing to
fetch/parse only drops that one article's time to None, never fails
the whole source.
"""

import logging
import re
from datetime import datetime
from typing import List, Optional

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, CrawlerError
from models import NewsItem
from utils import normalize_title, normalize_url

logger = logging.getLogger(__name__)

_POST_TIME_RE = re.compile(r"(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2})")


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

        urls_by_title = {}
        for link in soup.select(self._TITLE_SELECTOR):
            title = normalize_title(link.get_text())
            href = link.get("href")
            if not title or not href:
                continue
            url = normalize_url(href, base_url=self.source_url)
            urls_by_title.setdefault(url, title)

        if not urls_by_title:
            raise CrawlerError(
                f"{self.source_name}: no articles found — page structure may have changed"
            )

        items = [
            NewsItem(
                source=self.source_name,
                title=title,
                url=url,
                published_at=self._fetch_published_at(url),
            )
            for url, title in urls_by_title.items()
        ]
        missing = sum(1 for i in items if i.published_at is None)
        if missing:
            logger.debug("%s: %d/%d article(s) still missing a time after visiting their page.",
                         self.source_name, missing, len(items))
        return items

    def _fetch_published_at(self, article_url: str) -> Optional[datetime]:
        """Best-effort: visit the article's own page for its
        `.post-time` text (e.g. "- 16/09/2026 09:43"). Any failure here
        (network, missing element, unparseable text) just means this
        one article keeps published_at=None — never raises, since a
        single flaky article page must not take down the whole source.
        """
        try:
            raw = self._fetch(article_url)
        except CrawlerError:
            return None
        try:
            soup = BeautifulSoup(raw, "html.parser")
        except Exception:  # noqa: BLE001 - a parser bug must not crash the app
            return None

        el = soup.select_one(".post-time")
        if el is None:
            return None
        match = _POST_TIME_RE.search(el.get_text())
        if not match:
            return None
        try:
            naive = datetime.strptime(match.group(1), "%d/%m/%Y %H:%M")
        except ValueError:
            return None
        return naive.replace(tzinfo=self.tz)

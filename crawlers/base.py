"""Crawler interfaces.

BaseCrawler is the contract from PROJECT SPEC section 19: every
crawler exposes source_name/source_url and a crawl() returning
List[NewsItem]. Nothing else in the app (database, telegram) needs to
know which subclass produced the data. It also owns the HTTP fetch
(timeout, retry, User-Agent per spec section 13) shared by every
concrete crawler regardless of whether it parses RSS or scrapes HTML.

RSSCrawlerBase is a shared implementation for the common case (most of
this project's sources publish an RSS feed that matches the requested
category exactly — see README "Vì sao dùng RSS cho cả 14 nguồn"). It
handles RSS parsing so each site file only needs to declare its feed
URL. A site with no suitable RSS subclasses BaseCrawler directly and
overrides `crawl()` to scrape HTML with BeautifulSoup instead (see
crawlers/cafebiz.py for an example) — nothing else in the app needs to
know the difference.
"""

import calendar
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import List, Optional
from zoneinfo import ZoneInfo

import feedparser
import requests

from models import NewsItem
from utils import normalize_title, normalize_url

logger = logging.getLogger(__name__)


class CrawlerError(Exception):
    """Raised when a source could not be crawled at all this cycle.

    This is deliberately distinct from "crawled successfully but found
    0 articles" (spec section 1.6: a source error must never be
    reported as "no new articles").
    """


class BaseCrawler(ABC):
    source_name: str
    source_url: str
    timezone_name: str = "Asia/Ho_Chi_Minh"

    def __init__(
        self,
        timeout: int = 15,
        max_retries: int = 3,
        user_agent: str = "NewsMonitor/1.0",
    ):
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent
        self.tz = ZoneInfo(self.timezone_name)

    @abstractmethod
    def crawl(self) -> List[NewsItem]:
        raise NotImplementedError

    def _fetch(self, url: str) -> bytes:
        headers = {"User-Agent": self.user_agent}
        last_exc: Optional[Exception] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                resp = requests.get(url, headers=headers, timeout=self.timeout)
                resp.raise_for_status()
                return resp.content
            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "%s: fetch attempt %d/%d failed: %s",
                    self.source_name,
                    attempt,
                    self.max_retries,
                    exc,
                )
                if attempt < self.max_retries:
                    time.sleep(min(2**attempt, 10))
        raise CrawlerError(
            f"{self.source_name}: failed to fetch {url} after {self.max_retries} attempts: {last_exc}"
        )


class RSSCrawlerBase(BaseCrawler):
    """Shared RSS-based crawl implementation.

    Subclasses set: source_name, source_url (the human category page,
    used only for display/error messages), feed_url.
    """

    feed_url: str

    def crawl(self) -> List[NewsItem]:
        raw = self._fetch(self.feed_url)
        raw = self._preprocess_raw(raw)
        parsed = feedparser.parse(raw)

        if parsed.bozo and not parsed.entries:
            raise CrawlerError(
                f"Feed for {self.source_name} could not be parsed: {parsed.bozo_exception}"
            )

        items: List[NewsItem] = []
        for entry in parsed.entries:
            title = normalize_title(getattr(entry, "title", "") or "")
            link = normalize_url(getattr(entry, "link", "") or "", base_url=self.feed_url)
            if not title or not link:
                # Skip malformed entries rather than failing the whole
                # source over one bad item.
                continue
            published_at = self._extract_published_at(entry)
            items.append(
                NewsItem(
                    source=self.source_name,
                    title=title,
                    url=link,
                    published_at=published_at,
                )
            )
        return items

    def _preprocess_raw(self, raw: bytes) -> bytes:
        """Hook for a subclass to fix up the raw feed bytes before
        they're handed to feedparser — e.g. a feed whose XML prolog
        declares the wrong encoding (see VietnamBizCrawler). No-op by
        default."""
        return raw

    def _extract_published_at(self, entry) -> Optional[datetime]:
        struct = getattr(entry, "published_parsed", None) or getattr(
            entry, "updated_parsed", None
        )
        if not struct:
            return None
        try:
            # feedparser normalizes *_parsed to a UTC time.struct_time
            # regardless of the feed's original offset/format (this is
            # what lets us handle VnExpress's full 4-digit-year offset
            # dates and CafeF/Thanh Nien's 2-digit-year dates uniformly
            # without hand-parsing each site's date string).
            utc_dt = datetime.fromtimestamp(calendar.timegm(struct), tz=timezone.utc)
            return utc_dt.astimezone(self.tz)
        except (OverflowError, ValueError):
            return None

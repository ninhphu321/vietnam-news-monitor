"""Bao Chinh Phu (Vietnam Government Web Portal) crawler.

Audit (2026-09-14): https://baochinhphu.vn/kinh-te.htm corresponds to
RSS feed https://baochinhphu.vn/kinh-te.rss (found via the category
page's declared <link rel="alternate">) — verified live and on-topic.
This is the official government portal — the most "chính thống"
source available for this project.

One real quirk: unlike every other source here, this feed's <pubDate>
is NOT RFC-822 (e.g. "9/14/2026 6:44:00 PM" instead of "Mon, 14 Sep
2026 18:44:00 +0700"), so feedparser cannot populate published_parsed
for it (verified: parsed.entries[i].published_parsed is None). Without
the override below, every article from this source would silently
have published_at=None forever. _extract_published_at() falls back to
parsing that exact format by hand only when the base class's normal
RFC-822 handling comes back empty.
"""

from datetime import datetime
from typing import Optional

from crawlers.base import RSSCrawlerBase

_DATE_FORMAT = "%m/%d/%Y %I:%M:%S %p"


class BaoChinhPhuCrawler(RSSCrawlerBase):
    source_name = "Chính phủ"
    source_url = "https://baochinhphu.vn/kinh-te.htm"
    feed_url = "https://baochinhphu.vn/kinh-te.rss"

    def _extract_published_at(self, entry) -> Optional[datetime]:
        parsed = super()._extract_published_at(entry)
        if parsed is not None:
            return parsed

        raw = getattr(entry, "published", None)
        if not raw:
            return None
        try:
            naive = datetime.strptime(raw, _DATE_FORMAT)
        except ValueError:
            return None
        return naive.replace(tzinfo=self.tz)

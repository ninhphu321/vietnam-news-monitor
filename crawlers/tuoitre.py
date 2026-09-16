"""Tuoi Tre crawler.

Audit (2026-09-14): https://tuoitre.vn/kinh-doanh.htm corresponds
exactly to RSS feed https://tuoitre.vn/rss/kinh-doanh.rss — verified
live.

Audit (2026-09-16): every article on the website showed up with no
time ("--:--"). Root cause: <pubDate> now reads e.g.
"9/16/2026 10:17:00 AM" — US month/day/year, 12-hour clock, and a
narrow no-break space (U+202F, not a plain space) before AM/PM — none
of which feedparser's date parser recognizes, so published_parsed was
silently None for every entry. Parsed by hand below.
"""

from datetime import datetime
from typing import Optional

from crawlers.base import RSSCrawlerBase


class TuoiTreCrawler(RSSCrawlerBase):
    source_name = "Tuổi Trẻ"
    source_url = "https://tuoitre.vn/kinh-doanh.htm"
    feed_url = "https://tuoitre.vn/rss/kinh-doanh.rss"

    def _extract_published_at(self, entry) -> Optional[datetime]:
        parsed = super()._extract_published_at(entry)
        if parsed is not None:
            return parsed

        raw = getattr(entry, "published", None)
        if not raw:
            return None
        # U+202F (narrow no-break space) and U+00A0 (non-breaking space)
        # both show up before AM/PM depending on how the page was
        # generated; normalize either to a plain space for strptime.
        normalized = raw.replace(" ", " ").replace(" ", " ").strip()
        try:
            naive = datetime.strptime(normalized, "%m/%d/%Y %I:%M:%S %p")
        except ValueError:
            return None
        return naive.replace(tzinfo=self.tz)

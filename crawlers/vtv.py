"""VTV (Vietnam Television) crawler.

Audit (2026-09-14): the "obvious" guess https://vtv.vn/kinh-te.rss
returns HTTP 404. The correct feed was found via the category page
https://vtv.vn/kinh-te.htm's declared <link rel="alternate">:
https://vtv.vn/rss/kinh-te.rss — verified live and on-topic. VTV is
the national state television broadcaster — "chính thống" source
request.

One real quirk: VTV's <pubDate> uses a truncated UTC offset — "+07"
instead of the RFC-822-correct "+0700" (verified against the live
feed, not just a one-off fixture glitch) — which feedparser's date
parser rejects outright, so published_parsed is always None for this
source without the override below. VTV's offset is always this same
+07 (Vietnam time), so it's safe to strip it and attach self.tz
directly rather than trying to generically parse an arbitrary offset.
"""

import re
from datetime import datetime
from typing import Optional

from crawlers.base import RSSCrawlerBase

_TRUNCATED_OFFSET = re.compile(r"^(.*)\s+\+07$")


class VTVCrawler(RSSCrawlerBase):
    source_name = "VTV"
    source_url = "https://vtv.vn/kinh-te.htm"
    feed_url = "https://vtv.vn/rss/kinh-te.rss"

    def _extract_published_at(self, entry) -> Optional[datetime]:
        parsed = super()._extract_published_at(entry)
        if parsed is not None:
            return parsed

        raw = getattr(entry, "published", None)
        if not raw:
            return None
        match = _TRUNCATED_OFFSET.match(raw.strip())
        if not match:
            return None
        try:
            naive = datetime.strptime(match.group(1), "%a, %d %b %Y %H:%M:%S")
        except ValueError:
            return None
        return naive.replace(tzinfo=self.tz)

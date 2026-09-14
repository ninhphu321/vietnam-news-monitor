"""CafeF crawler.

Audit (2026-09-14): https://cafef.vn/tai-chinh-ngan-hang.chn
corresponds exactly to RSS feed
https://cafef.vn/tai-chinh-ngan-hang.rss — verified live. Note CafeF's
pubDate uses a 2-digit year (e.g. "Mon, 14 Sep 26 08:00:00 +0700");
feedparser resolves this to 2026 correctly via published_parsed, so no
special-casing is needed here (see RSSCrawlerBase._extract_published_at).
"""

from crawlers.base import RSSCrawlerBase


class CafeFCrawler(RSSCrawlerBase):
    source_name = "CafeF"
    source_url = "https://cafef.vn/tai-chinh-ngan-hang.chn"
    feed_url = "https://cafef.vn/tai-chinh-ngan-hang.rss"

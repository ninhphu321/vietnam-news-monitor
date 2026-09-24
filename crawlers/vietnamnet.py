"""VietnamNet crawler.

Audit (2026-09-24): https://vietnamnet.vn/kinh-doanh corresponds to
RSS feed https://vietnamnet.vn/rss/kinh-doanh.rss — verified live,
RFC-822 pubDate with +0700 offset. The feed is unusually large (~1000
items, mostly old); dedup by URL makes that harmless. (VietnamNet was
previously dropped after a silently-stale feed incident — the existing
stale-source alert covers a repeat of that.)
"""

from crawlers.base import RSSCrawlerBase


class VietnamNetCrawler(RSSCrawlerBase):
    source_name = "VietnamNet"
    source_url = "https://vietnamnet.vn/kinh-doanh"
    feed_url = "https://vietnamnet.vn/rss/kinh-doanh.rss"

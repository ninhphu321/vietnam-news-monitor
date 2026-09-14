"""VnExpress crawler.

Audit (2026-09-14): https://vnexpress.net/kinh-doanh corresponds
exactly to RSS feed https://vnexpress.net/rss/kinh-doanh.rss —
verified live, pubDate is a full RFC-822 string with explicit +0700
offset, e.g. "Mon, 14 Sep 2026 09:43:55 +0700".
"""

from crawlers.base import RSSCrawlerBase


class VnExpressCrawler(RSSCrawlerBase):
    source_name = "VnExpress"
    source_url = "https://vnexpress.net/kinh-doanh"
    feed_url = "https://vnexpress.net/rss/kinh-doanh.rss"

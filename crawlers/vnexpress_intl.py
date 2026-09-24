"""VnExpress International (English) business crawler.

Audit (2026-09-24): https://e.vnexpress.net/rss/business.rss — verified
live, RFC-822 pubDate with +0700 offset. English headlines: they show
up in the news stream and per-source columns, but the Vietnamese-keyword
Issue Intelligence engine (web/issues.py) won't group them into issues.
"""

from crawlers.base import RSSCrawlerBase


class VnExpressIntlCrawler(RSSCrawlerBase):
    source_name = "VnExpress Intl"
    source_url = "https://e.vnexpress.net/news/business"
    feed_url = "https://e.vnexpress.net/rss/business.rss"

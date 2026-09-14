"""Znews crawler.

Audit (2026-09-14): https://znews.vn/kinh-doanh-tai-chinh.html
corresponds to RSS feed
https://znews.vn/rss/kinh-doanh-tai-chinh.rss — verified live,
absolute URLs, 4-digit-year pubDate, no tracking params.
"""

from crawlers.base import RSSCrawlerBase


class ZnewsCrawler(RSSCrawlerBase):
    source_name = "Znews"
    source_url = "https://znews.vn/kinh-doanh-tai-chinh.html"
    feed_url = "https://znews.vn/rss/kinh-doanh-tai-chinh.rss"

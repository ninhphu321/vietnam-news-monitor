"""Người Quan Sát crawler.

Audit (2026-09-24): the site advertises https://nguoiquansat.vn/rss/trang-chu
via <link rel="alternate">; verified live — finance/business/real-estate
focused, ~40 items, RFC-822 pubDate with +0700 offset, absolute URLs.
"""

from crawlers.base import RSSCrawlerBase


class NguoiQuanSatCrawler(RSSCrawlerBase):
    source_name = "Người Quan Sát"
    source_url = "https://nguoiquansat.vn"
    feed_url = "https://nguoiquansat.vn/rss/trang-chu"

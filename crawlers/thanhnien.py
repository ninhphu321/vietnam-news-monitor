"""Thanh Nien crawler.

Audit (2026-09-14): https://thanhnien.vn/kinh-te.htm corresponds
exactly to RSS feed https://thanhnien.vn/rss/kinh-te.rss — verified
live.
"""

from crawlers.base import RSSCrawlerBase


class ThanhNienCrawler(RSSCrawlerBase):
    source_name = "Thanh Niên"
    source_url = "https://thanhnien.vn/kinh-te.htm"
    feed_url = "https://thanhnien.vn/rss/kinh-te.rss"

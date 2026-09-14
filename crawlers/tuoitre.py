"""Tuoi Tre crawler.

Audit (2026-09-14): https://tuoitre.vn/kinh-doanh.htm corresponds
exactly to RSS feed https://tuoitre.vn/rss/kinh-doanh.rss — verified
live.
"""

from crawlers.base import RSSCrawlerBase


class TuoiTreCrawler(RSSCrawlerBase):
    source_name = "Tuổi Trẻ"
    source_url = "https://tuoitre.vn/kinh-doanh.htm"
    feed_url = "https://tuoitre.vn/rss/kinh-doanh.rss"

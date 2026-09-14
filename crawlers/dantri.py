"""Dan Tri crawler.

Audit (2026-09-14): https://dantri.com.vn/kinh-doanh corresponds to
RSS feed https://dantri.com.vn/rss/kinh-doanh.rss — verified live,
absolute URLs, 4-digit-year pubDate, no tracking params.
"""

from crawlers.base import RSSCrawlerBase


class DanTriCrawler(RSSCrawlerBase):
    source_name = "Dân Trí"
    source_url = "https://dantri.com.vn/kinh-doanh"
    feed_url = "https://dantri.com.vn/rss/kinh-doanh.rss"

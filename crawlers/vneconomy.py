"""VnEconomy crawler.

Audit (2026-09-14): VnEconomy has no single generic "kinh te" RSS —
https://vneconomy.vn/rss/home.rss returns an empty "No Content" feed.
The live, correctly-scoped feed is the Tai chinh (Finance) category:
https://vneconomy.vn/tai-chinh.rss — verified live, absolute URLs,
4-digit-year pubDate, no tracking params.
"""

from crawlers.base import RSSCrawlerBase


class VnEconomyCrawler(RSSCrawlerBase):
    source_name = "VnEconomy"
    source_url = "https://vneconomy.vn/tai-chinh"
    feed_url = "https://vneconomy.vn/tai-chinh.rss"

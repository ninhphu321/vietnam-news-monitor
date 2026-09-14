"""VietnamPlus crawler.

Audit (2026-09-14): https://www.vietnamplus.vn/kinhte corresponds to
RSS feed https://www.vietnamplus.vn/rss/kinhte.rss — verified live,
on-topic, absolute URLs, 4-digit-year pubDate (gzip-compressed
response; requests handles this transparently, unlike the raw curl
probe which needed --compressed). VietnamPlus is run by TTXVN (Vietnam
News Agency, the state news agency) — "chính thống" source request.
"""

from crawlers.base import RSSCrawlerBase


class VietnamPlusCrawler(RSSCrawlerBase):
    source_name = "VietnamPlus"
    source_url = "https://www.vietnamplus.vn/kinhte"
    feed_url = "https://www.vietnamplus.vn/rss/kinhte.rss"

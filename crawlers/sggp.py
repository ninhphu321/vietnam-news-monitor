"""Báo Sài Gòn Giải Phóng (economy section) crawler.

Audit (2026-09-24): the feed list at https://www.sggp.org.vn/rss.html
shows "kinh-te-89.rss" is the real "Kinh tế" section. Beware: the
similarly named "kinhte-3.rss" is actually the "Đô thị" (urban) feed.
pubDate uses "+07:00" (with colon) — parsed fine by feedparser.
"""

from crawlers.base import RSSCrawlerBase


class SGGPCrawler(RSSCrawlerBase):
    source_name = "SGGP"
    source_url = "https://www.sggp.org.vn/kinhte/"
    feed_url = "https://www.sggp.org.vn/rss/kinh-te-89.rss"

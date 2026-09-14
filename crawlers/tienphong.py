"""Tien Phong crawler.

Audit (2026-09-14): the "obvious" guess https://tienphong.vn/rss/kinh-te-108.rss
returns HTTP 200 but is NOT the economy category — its items are a mixed
general feed (entertainment, education, real estate). The correct
economy feed was found by reading the site's own RSS index at
https://tienphong.vn/rss.html, which lists
https://tienphong.vn/rss/kinh-te-3.rss as the "Kinh te" category —
verified live, on-topic, absolute URLs, 4-digit-year pubDate.
"""

from crawlers.base import RSSCrawlerBase


class TienPhongCrawler(RSSCrawlerBase):
    source_name = "Tiền Phong"
    source_url = "https://tienphong.vn/kinh-te.html"
    feed_url = "https://tienphong.vn/rss/kinh-te-3.rss"

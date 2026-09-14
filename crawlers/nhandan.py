"""Nhan Dan (Communist Party official newspaper) crawler.

Audit (2026-09-14): the "obvious" guess https://nhandan.vn/rss/kinhte-1041.rss
returns HTTP 200 but is NOT the economy category — its items are a
mixed general feed (irrigation projects, fire drills, a royal visit).
The correct feed was found by reading the actual category page
https://nhandan.vn/kinhte.htm, whose declared
<link rel="alternate" type="application/rss+xml"> points to
https://nhandan.vn/rss/kinhte-1185.rss — verified live and on-topic
(finance/market/policy articles), though Nhan Dan's own "Kinh te"
category is editorially broader than a pure business vertical (some
adjacent social-policy items appear too — that is their own official
categorization, not a crawler mistake).
"""

from crawlers.base import RSSCrawlerBase


class NhanDanCrawler(RSSCrawlerBase):
    source_name = "Nhân Dân"
    source_url = "https://nhandan.vn/kinhte.htm"
    feed_url = "https://nhandan.vn/rss/kinhte-1185.rss"

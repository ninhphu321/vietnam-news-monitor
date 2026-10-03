"""Người Quan Sát crawler.

Audit (2026-09-24): the site advertises https://nguoiquansat.vn/rss/trang-chu
via <link rel="alternate">; verified live — finance/business/real-estate
focused, ~40 items, RFC-822 pubDate with +0700 offset, absolute URLs.

Re-audit (2026-10-03, economy-only review): that homepage feed is NOT
economy-only — 23 of its 40 items appeared in none of the site's
economy category feeds and were party-discipline, crime, education,
foreign-military and human-interest stories ("Khai trừ Đảng...",
"Tìm con mất tích...", "Loạt tiêm kích Nga diễn tập..."). The outlet has
no single economy feed, but it does publish per-category feeds, all
verified live (200, 40 items each, same format): so this source now
merges the five economy ones instead of the catch-all homepage feed.
"""

from crawlers.base import RSSCrawlerBase


class NguoiQuanSatCrawler(RSSCrawlerBase):
    source_name = "Người Quan Sát"
    source_url = "https://nguoiquansat.vn"
    feed_url = "https://nguoiquansat.vn/rss/tai-chinh-ngan-hang"
    extra_feed_urls = (
        "https://nguoiquansat.vn/rss/vi-mo",
        "https://nguoiquansat.vn/rss/doanh-nghiep",
        "https://nguoiquansat.vn/rss/chung-khoan",
        "https://nguoiquansat.vn/rss/bat-dong-san",
    )

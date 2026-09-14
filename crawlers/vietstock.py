"""Vietstock crawler.

Originally scoped to the Tai chinh/Ngan hang category (id 757, RSS at
https://vietstock.vn/757/tai-chinh/ngan-hang.rss) per the V1 spec.

Changed 2026-09-14 at user request: the user was checking
https://vietstock.vn/chu-de/1-2/moi-cap-nhat.htm ("Diem tin: Moi cap
nhat"), Vietstock's site-wide latest-news digest covering every
category (Chung khoan, Doanh nghiep, Bat dong san, Tai chinh, Hang
hoa, Kinh te, The gioi...), not just banking — so the narrow feed
never matched what they were watching. Switched to Vietstock's own
site-wide feed, https://vietstock.vn/0/tin-moi.rss ("Tin moi"),
verified live and matching that page's content. This intentionally
increases volume a lot (all categories, not just banking).
"""

from crawlers.base import RSSCrawlerBase


class VietstockCrawler(RSSCrawlerBase):
    source_name = "Vietstock"
    source_url = "https://vietstock.vn/chu-de/1-2/moi-cap-nhat.htm"
    feed_url = "https://vietstock.vn/0/tin-moi.rss"

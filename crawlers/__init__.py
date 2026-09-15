"""Crawler package.

ALL_CRAWLERS is the single list the rest of the app (scheduler.py)
iterates over. Adding a 6th source in the future means: add a new
crawlers/<site>.py, append it here — nothing else changes.
"""

from crawlers.baochinhphu import BaoChinhPhuCrawler
from crawlers.cafef import CafeFCrawler
from crawlers.dantri import DanTriCrawler
from crawlers.nhandan import NhanDanCrawler
from crawlers.thanhnien import ThanhNienCrawler
from crawlers.tienphong import TienPhongCrawler
from crawlers.tuoitre import TuoiTreCrawler
from crawlers.vietnambiz import VietnamBizCrawler
from crawlers.vietnamplus import VietnamPlusCrawler
from crawlers.vietstock import VietstockCrawler
from crawlers.vneconomy import VnEconomyCrawler
from crawlers.vnexpress import VnExpressCrawler
from crawlers.vtv import VTVCrawler
from crawlers.znews import ZnewsCrawler

CRAWLER_CLASSES = [
    VnExpressCrawler,
    TuoiTreCrawler,
    CafeFCrawler,
    VietstockCrawler,
    ThanhNienCrawler,
    DanTriCrawler,
    VnEconomyCrawler,
    ZnewsCrawler,
    TienPhongCrawler,
    VietnamPlusCrawler,
    NhanDanCrawler,
    BaoChinhPhuCrawler,
    VTVCrawler,
    VietnamBizCrawler,
]

__all__ = ["CRAWLER_CLASSES"]

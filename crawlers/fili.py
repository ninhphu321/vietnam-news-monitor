"""FiLi (fili.vn) — "Ngân hàng và Bảo hiểm" — HTML scraping (no RSS).

History: the first version (audit 2026-09-16) POSTed to the AngularJS
SPA's `/_Partials/ListPageArticle` JSON endpoint, because the category
page then rendered its article list client-side only.

Audit (2026-10-03): that endpoint now answers HTTP 405 on POST (404 on
GET) — the site was rebuilt and the category page
(`/ngan-hang-bao-hiem.htm`) now ships its article list as plain
server-rendered HTML, so a plain GET + BeautifulSoup fetch works and the
JSON route is gone. Found by a live crawl of all 23 sources while
re-auditing the feeds (FiLi was the only one failing); no RSS exists
(`.rss` variants all 404, no `<link rel="alternate">`).

Markup, per article:

    <article class="search-card-item">
      <h3 class="search-card-title"><a href="/2026/10/<slug>-757-1498696.htm">TITLE</a></h3>
      <div class="search-card-meta"><time>4 giờ trước</time></div>

`<time>` has no machine-readable attribute and comes in two human
forms: relative ("4 phút/giờ/ngày trước", resolved against the crawl
moment — accurate to the unit shown) and absolute ("02/10/2026 20:58")
for older items. Anything else is left published_at=None, like Báo Đầu
tư (the site then falls back to first_seen_at).
"""

import re
from datetime import datetime, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

from crawlers.base import BaseCrawler, CrawlerError
from models import NewsItem
from utils import normalize_title, normalize_url

_TZ = ZoneInfo("Asia/Ho_Chi_Minh")
_RELATIVE_RE = re.compile(r"^(\d+)\s*(phút|giờ|ngày)\s*trước$")
_UNIT = {"phút": "minutes", "giờ": "hours", "ngày": "days"}


class FiliCrawler(BaseCrawler):
    source_name = "FiLi"
    source_url = "https://fili.vn/ngan-hang-bao-hiem.htm"

    def crawl(self) -> List[NewsItem]:
        raw = self._fetch(self.source_url)
        try:
            soup = BeautifulSoup(raw, "html.parser")
        except Exception as exc:  # noqa: BLE001 - a parser bug must not crash the app
            raise CrawlerError(f"{self.source_name}: failed to parse HTML: {exc}") from None

        now = datetime.now(_TZ)
        items_by_url = {}
        for card in soup.select("article.search-card-item"):
            link = card.select_one(".search-card-title a")
            if link is None:
                continue
            title = normalize_title(link.get_text())
            href = link.get("href")
            if not title or not href:
                continue
            time_el = card.select_one("time")
            published_at = self._parse_time(time_el.get_text(strip=True) if time_el else None, now)
            url = normalize_url(href, base_url=self.source_url)
            items_by_url.setdefault(
                url,
                NewsItem(source=self.source_name, title=title, url=url, published_at=published_at),
            )

        if not items_by_url:
            raise CrawlerError(
                f"{self.source_name}: no articles found — page structure may have changed"
            )
        return list(items_by_url.values())

    @staticmethod
    def _parse_time(raw: Optional[str], now: datetime) -> Optional[datetime]:
        if not raw:
            return None
        relative = _RELATIVE_RE.match(raw)
        if relative:
            return now - timedelta(**{_UNIT[relative.group(2)]: int(relative.group(1))})
        try:
            return datetime.strptime(raw, "%d/%m/%Y %H:%M").replace(tzinfo=_TZ)
        except ValueError:
            return None

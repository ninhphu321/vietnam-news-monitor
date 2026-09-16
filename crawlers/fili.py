"""FiLi (fili.vn) — "Ngân hàng và Bảo hiểm" — JSON API, no RSS/HTML scraping.

Audit (2026-09-16): the category page (`/ngan-hang-bao-hiem.htm`) is an
AngularJS single-page app — the article list (`ng-repeat` template) is
empty in the raw HTML and only filled in client-side, so a plain
GET+BeautifulSoup fetch would always return 0 articles. Found the real
data source by loading the page in a real browser and inspecting its
network requests: it POSTs to `/_Partials/ListPageArticle` and gets
back clean JSON — more reliable than scraping HTML would have been
anyway, since there's no markup to break.

Two real quirks in that payload, found by capturing the page's own
request (guessing plausible field values first returned an empty
`LsArticles: []` every time):

1. `channelid` is not the category's own ID (734) — it's a
   comma-delimited string of that ID *plus all its sub-category IDs*,
   with leading/trailing commas: `",734,757,3113,758,"`. Sending just
   734 alone matches nothing, since articles are tagged with a
   sub-category ID (e.g. 757 for "Ngân hàng"), never the umbrella 734.
2. `PublishTime` is in ASP.NET's JSON date format,
   `"/Date(1789558294227)/"` — milliseconds since the Unix epoch
   (UTC), not an ISO string.
"""

import re
from datetime import datetime, timezone
from typing import List, Optional

from crawlers.base import BaseCrawler, CrawlerError
from models import NewsItem
from utils import normalize_title, normalize_url

_API_URL = "https://fili.vn/_Partials/ListPageArticle"
# "Ngân hàng và Bảo hiểm" (734) plus its sub-categories — captured from
# the site's own request, not guessed (see module docstring).
_CHANNEL_IDS = ",734,757,3113,758,"
_DOTNET_DATE_RE = re.compile(r"/Date\((\d+)\)/")


class FiliCrawler(BaseCrawler):
    source_name = "FiLi"
    source_url = "https://fili.vn/ngan-hang-bao-hiem.htm"

    def crawl(self) -> List[NewsItem]:
        data = self._post_json(
            _API_URL, {"item": 50, "page": 1, "channelid": _CHANNEL_IDS}
        )
        try:
            raw_articles = data["LsArticles"]
        except (KeyError, TypeError) as exc:
            raise CrawlerError(
                f"{self.source_name}: unexpected API response shape: {exc}"
            ) from None

        items_by_url = {}
        for article in raw_articles:
            title = normalize_title(article.get("Title") or "")
            href = article.get("URL")
            if not title or not href:
                continue
            url = normalize_url(href, base_url=self.source_url)
            items_by_url.setdefault(
                url,
                NewsItem(
                    source=self.source_name,
                    title=title,
                    url=url,
                    published_at=self._parse_time(article.get("PublishTime")),
                ),
            )

        if not items_by_url:
            raise CrawlerError(
                f"{self.source_name}: no articles found — API response shape may have changed"
            )
        return list(items_by_url.values())

    def _parse_time(self, raw: Optional[str]) -> Optional[datetime]:
        if not raw:
            return None
        match = _DOTNET_DATE_RE.search(raw)
        if not match:
            return None
        millis = int(match.group(1))
        return datetime.fromtimestamp(millis / 1000, tz=timezone.utc).astimezone(self.tz)

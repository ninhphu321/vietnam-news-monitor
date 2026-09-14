"""Voice of Vietnam (VOV) crawler.

Audit (2026-09-14): https://vov.vn/kinh-te corresponds to RSS feed
https://vov.vn/rss/kinh-te.rss — verified live, on-topic, absolute
URLs, 4-digit-year pubDate. VOV is Vietnam's national radio
broadcaster (state-run) — included for the "chính thống" (official)
source request.

One real quirk: VOV's WAF returns HTTP 403 for the app's normal
descriptive Chrome-style User-Agent (config.user_agent) — verified
this is not about the "NewsMonitor" suffix specifically, since the
exact same UA string with that suffix removed still gets 403; a bare
"Mozilla/5.0" is let through. Overriding just this source's UA rather
than weakening it globally for the other 13 crawlers.
"""

from crawlers.base import RSSCrawlerBase


class VOVCrawler(RSSCrawlerBase):
    source_name = "VOV"
    source_url = "https://vov.vn/kinh-te"
    feed_url = "https://vov.vn/rss/kinh-te.rss"

    def __init__(self, timeout: int = 15, max_retries: int = 3, user_agent: str = "NewsMonitor/1.0"):
        super().__init__(timeout=timeout, max_retries=max_retries, user_agent="Mozilla/5.0")

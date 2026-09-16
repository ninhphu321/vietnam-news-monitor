"""VietnamBiz crawler.

Audit (2026-09-15): https://vietnambiz.vn/tai-chinh corresponds to RSS
feed https://vietnambiz.vn/tai-chinh.rss — verified live and on-topic
(tỷ giá, ngân hàng, tín dụng...). Its <title> also double-encodes
accented characters inside CDATA (e.g. "gi&#225;" instead of "giá"),
the same Thanh Nien quirk already fixed generically in
utils.normalize_title via html.unescape() — no extra work needed here.

One real quirk that does need handling: <pubDate> uses "GMT+7" instead
of the RFC-822-correct "+0700" (e.g. "Tue, 15 Sep 2026 09:02:15
GMT+7"), which feedparser's date parser rejects outright (verified:
published_parsed is None for every entry). VietnamBiz's offset is
always this same GMT+7 (Vietnam time), so it's safe to strip it and
attach self.tz directly.

Audit (2026-09-16): the feed started (or was always, missed at first
audit) failing outright with "not well-formed (invalid token)" —
root cause is the XML prolog declaring `encoding="utf-16"` while the
actual bytes are UTF-8 (verified: no null bytes between ASCII
characters, which real UTF-16 would have). Python's expat parser
trusts the declared encoding and chokes on the mismatch. Since the
bytes are genuinely UTF-8, the fix is just correcting that one
declared attribute before parsing, not decoding/re-encoding anything.
"""

import re
from datetime import datetime
from typing import Optional

from crawlers.base import RSSCrawlerBase

_GMT7_SUFFIX = re.compile(r"^(.*)\s+GMT\+7$")
_WRONG_ENCODING_DECL = re.compile(rb"encoding=[\"']utf-16[\"']", re.IGNORECASE)


class VietnamBizCrawler(RSSCrawlerBase):
    source_name = "VietnamBiz"
    source_url = "https://vietnambiz.vn/tai-chinh"
    feed_url = "https://vietnambiz.vn/tai-chinh.rss"

    def _preprocess_raw(self, raw: bytes) -> bytes:
        return _WRONG_ENCODING_DECL.sub(b'encoding="utf-8"', raw, count=1)

    def _extract_published_at(self, entry) -> Optional[datetime]:
        parsed = super()._extract_published_at(entry)
        if parsed is not None:
            return parsed

        raw = getattr(entry, "published", None)
        if not raw:
            return None
        match = _GMT7_SUFFIX.match(raw.strip())
        if not match:
            return None
        try:
            naive = datetime.strptime(match.group(1), "%a, %d %b %Y %H:%M:%S")
        except ValueError:
            return None
        return naive.replace(tzinfo=self.tz)

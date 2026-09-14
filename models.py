"""Data models shared across crawlers, database, and Telegram layers.

Keeping this a single small dataclass is intentional: every crawler
returns a list of NewsItem, and nothing downstream (database.py,
telegram.py) needs to know which site produced it.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class NewsItem:
    """One article as scraped from a source, before/after normalization.

    Attributes:
        source: Human-readable source name, e.g. "VnExpress".
        title: Article headline, whitespace-normalized.
        url: Absolute article URL. Normalized (tracking params stripped)
            by the time this is handed to database.py.
        published_at: Timezone-aware datetime in Asia/Ho_Chi_Minh, or
            None if the source did not provide a usable timestamp.
    """

    source: str
    title: str
    url: str
    published_at: Optional[datetime] = None

    def __repr__(self) -> str:  # pragma: no cover - cosmetic only
        ts = self.published_at.strftime("%Y-%m-%d %H:%M") if self.published_at else "?"
        return f"NewsItem({self.source!r}, {ts}, {self.title!r})"

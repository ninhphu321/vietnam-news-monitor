"""SQLite persistence layer.

Schema follows PROJECT SPEC section 15, plus an `initial_seen` column
(section 15 explicitly allows adding this) used to mark articles that
were captured during first-run baseline seeding (section 7) rather
than genuinely "sent" articles.

Design choices worth noting:
- One short-lived connection per call instead of one long-lived
  connection. APScheduler's BlockingScheduler runs jobs in a worker
  thread pool, and sqlite3 connections are not safe to share across
  threads by default; opening per-call avoids that whole class of bug
  for a workload of "a few dozen rows every 30 minutes" where the
  connection overhead is irrelevant.
- `insert_if_new` uses INSERT OR IGNORE + rowcount to make the
  "check URL exists -> insert" step from spec section 16 atomic
  against the UNIQUE constraint, instead of a separate SELECT then
  INSERT (which would have a race window).
- Every timestamp is stored as an ISO-8601 string with UTC+7 offset,
  which sorts correctly as text and is unambiguous to parse back.
"""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set
from zoneinfo import ZoneInfo

from models import NewsItem
from utils import normalize_url

SCHEMA = """
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    published_at TEXT,
    first_seen_at TEXT NOT NULL,
    sent_at TEXT,
    initial_seen INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS source_health (
    source TEXT PRIMARY KEY,
    last_alerted_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, db_path: Path, timezone: str = "Asia/Ho_Chi_Minh"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.tz = ZoneInfo(timezone)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def is_empty(self) -> bool:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS c FROM news").fetchone()
            return row["c"] == 0

    def url_exists(self, url: str) -> bool:
        url = normalize_url(url)
        with self._connect() as conn:
            row = conn.execute("SELECT 1 FROM news WHERE url = ?", (url,)).fetchone()
            return row is not None

    def insert_if_new(self, item: NewsItem, initial_seen: bool = False) -> bool:
        """Insert `item` if its URL is not already known.

        Returns True if a new row was inserted, False if the URL
        already existed (nothing changed).
        """
        url = normalize_url(item.url)
        now = datetime.now(self.tz).isoformat()
        published_at = item.published_at.isoformat() if item.published_at else None

        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO news
                    (source, title, url, published_at, first_seen_at, sent_at, initial_seen)
                VALUES (?, ?, ?, ?, ?, NULL, ?)
                """,
                (item.source, item.title, url, published_at, now, int(initial_seen)),
            )
            return cur.rowcount == 1

    def mark_sent(self, urls: List[str], sent_at: Optional[datetime] = None) -> None:
        """Stamp sent_at for the given URLs. Only called after a confirmed
        successful Telegram send (spec section 16/17: crawl success is
        not telegram success)."""
        if not urls:
            return
        sent_at = sent_at or datetime.now(self.tz)
        with self._connect() as conn:
            conn.executemany(
                "UPDATE news SET sent_at = ? WHERE url = ?",
                [(sent_at.isoformat(), normalize_url(u)) for u in urls],
            )

    def get_pending(self) -> List[NewsItem]:
        """Articles already stored but never confirmed-sent (sent_at IS
        NULL), excluding baseline-seeded rows. These are re-offered to
        Telegram on the next cycle (spec section 17)."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT source, title, url, published_at
                FROM news
                WHERE sent_at IS NULL AND initial_seen = 0
                ORDER BY published_at DESC
                """
            ).fetchall()
        return [self._row_to_item(r) for r in rows]

    def _row_to_item(self, row: sqlite3.Row) -> NewsItem:
        published_at = None
        if row["published_at"]:
            published_at = datetime.fromisoformat(row["published_at"])
        return NewsItem(
            source=row["source"],
            title=row["title"],
            url=row["url"],
            published_at=published_at,
        )

    def count_all(self) -> int:
        with self._connect() as conn:
            return conn.execute("SELECT COUNT(*) AS c FROM news").fetchone()["c"]

    def known_sources(self) -> Set[str]:
        """Distinct source names that already have at least one row.

        Used to baseline-seed a source the first time it appears (e.g.
        a crawler added in a later release) without re-seeding sources
        that already have history — see scheduler.ensure_initial_baseline.
        """
        with self._connect() as conn:
            rows = conn.execute("SELECT DISTINCT source FROM news").fetchall()
        return {r["source"] for r in rows}

    def last_new_article_at(self, source: str) -> Optional[datetime]:
        """When `source` most recently contributed a genuinely new row
        (first_seen_at), regardless of initial_seen/sent_at.

        A source whose RSS feed has silently gone stale (still returns
        HTTP 200 but the same unchanged items every time — the real
        VietnamNet V2 incident) will never insert anything new, so this
        timestamp stops advancing. scheduler._detect_stale_sources uses
        that to flag it instead of relying on a human noticing.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(first_seen_at) AS ts FROM news WHERE source = ?", (source,)
            ).fetchone()
        if row is None or row["ts"] is None:
            return None
        return datetime.fromisoformat(row["ts"])

    def get_stale_alert(self, source: str) -> Optional[datetime]:
        """When we last sent a stale-source warning for `source`, or
        None if it isn't currently flagged (never alerted, or recovered
        and cleared)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT last_alerted_at FROM source_health WHERE source = ?", (source,)
            ).fetchone()
        return datetime.fromisoformat(row["last_alerted_at"]) if row else None

    def set_stale_alert(self, source: str, when: datetime) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO source_health (source, last_alerted_at) VALUES (?, ?)
                ON CONFLICT(source) DO UPDATE SET last_alerted_at = excluded.last_alerted_at
                """,
                (source, when.isoformat()),
            )

    def clear_stale_alert(self, source: str) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM source_health WHERE source = ?", (source,))

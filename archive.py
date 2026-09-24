"""Monthly archive of old articles.

    python main.py --archive-old [--archive-days 90] [--delete-archived]

Exports every article whose day is older than `keep_days` into one
gzip-compressed JSON-lines file per calendar month
(`data/archive/news-YYYY-MM.jsonl.gz`). By default it ONLY exports; the
rows stay in the database. Passing --delete-archived also removes them
from `news`, which shrinks the DB but has two real consequences:
  * those days disappear from the website's archive pages, and
  * a feed that still lists a deleted URL would be treated as "new" again
    (keep_days should comfortably exceed the longest feed history — the
    VietnamNet feed reaches back ~2 months).
Deliberately not wired into the CI workflow: archive files are not
stored on the db-state branch, so running it there would lose them.
"""

import gzip
import json
import logging
import sqlite3
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def archive_old_articles(
    db_path: Path, archive_dir: Path, keep_days: int, timezone: str, delete: bool = False,
    now: datetime = None,
) -> Dict[str, int]:
    """Returns {"YYYY-MM": rows written}. Re-running is safe: each month's
    file is rewritten from all of that month's old rows still in the DB
    (rows already deleted by an earlier --delete-archived run are kept in
    the existing file, which is merged by URL)."""
    now = now or datetime.now(ZoneInfo(timezone))
    cutoff = (now - timedelta(days=keep_days)).isoformat()
    archive_dir = Path(archive_dir)
    archive_dir.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT source, title, url, published_at, first_seen_at, sent_at, initial_seen
            FROM news
            WHERE COALESCE(published_at, first_seen_at) < ?
            ORDER BY COALESCE(published_at, first_seen_at)
            """,
            (cutoff,),
        ).fetchall()

        by_month: Dict[str, List[dict]] = defaultdict(list)
        for r in rows:
            month = (r["published_at"] or r["first_seen_at"])[:7]
            by_month[month].append(dict(r))

        written: Dict[str, int] = {}
        for month, items in by_month.items():
            path = archive_dir / f"news-{month}.jsonl.gz"
            merged = {}
            if path.exists():
                with gzip.open(path, "rt", encoding="utf-8") as fh:
                    for line in fh:
                        rec = json.loads(line)
                        merged[rec["url"]] = rec
            for rec in items:
                merged[rec["url"]] = rec
            with gzip.open(path, "wt", encoding="utf-8") as fh:
                for rec in merged.values():
                    fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            written[month] = len(items)

        if delete and rows:
            conn.executemany("DELETE FROM news WHERE url = ?", [(r["url"],) for r in rows])
            conn.commit()
            conn.execute("VACUUM")
            logger.info("Deleted %d archived article(s) from the database.", len(rows))
    finally:
        conn.close()

    logger.info("Archived %d article(s) into %d monthly file(s).", sum(written.values()), len(written))
    return written

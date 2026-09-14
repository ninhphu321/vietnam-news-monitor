"""SQLite backup: timestamped copy + retention pruning.

A plain file copy is safe to do while the app is running — SQLite only
holds short-lived locks per statement, not for the file's whole
lifetime, and `shutil.copy2` reads the file in one pass same as any
other reader would.
"""

import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import List
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)


def backup_database(db_path: Path, backup_dir: Path, keep_days: int, timezone: str = "Asia/Ho_Chi_Minh") -> Path:
    """Copy `db_path` into `backup_dir` with a timestamped name, then
    delete backups in that directory older than `keep_days`.

    Returns the path of the backup just created.
    """
    db_path = Path(db_path)
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    now = datetime.now(ZoneInfo(timezone))
    dest = backup_dir / f"{db_path.stem}-{now.strftime('%Y%m%d-%H%M%S')}{db_path.suffix}"
    shutil.copy2(db_path, dest)
    logger.info("Database backed up to %s", dest)

    removed = _prune_old_backups(backup_dir, db_path.stem, db_path.suffix, keep_days, now)
    if removed:
        logger.info("Pruned %d backup(s) older than %d day(s).", removed, keep_days)

    return dest


def _prune_old_backups(backup_dir: Path, stem: str, suffix: str, keep_days: int, now: datetime) -> int:
    cutoff = now.timestamp() - keep_days * 86400
    removed = 0
    for path in _list_backups(backup_dir, stem, suffix):
        if path.stat().st_mtime < cutoff:
            path.unlink()
            removed += 1
    return removed


def _list_backups(backup_dir: Path, stem: str, suffix: str) -> List[Path]:
    if not backup_dir.exists():
        return []
    return sorted(backup_dir.glob(f"{stem}-*{suffix}"))

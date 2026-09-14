"""Entry point / CLI.

    python main.py               # start the 15-minute scheduler (production)
    python main.py --run-once    # crawl immediately, once, then exit
    python main.py --dry-run     # crawl + dedup-check + print, no DB writes, no Telegram
    python main.py --backup-now  # timestamped SQLite backup, then exit (no crawl)

See README.md for full setup instructions.
"""

import argparse
import logging
import sys

from config import config
from database import Database
from logger import setup_logging
from scheduler import ensure_initial_baseline, run_backup, run_cycle, start_scheduler

logger = logging.getLogger(__name__)


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Vietnam News Monitor")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--run-once",
        action="store_true",
        help="Crawl immediately, once, then exit (does not wait for the scheduler).",
    )
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Crawl, parse, and check duplicates, printing results to the terminal. "
        "Never writes to the database and never sends Telegram messages.",
    )
    mode.add_argument(
        "--backup-now",
        action="store_true",
        help="Take a timestamped SQLite backup immediately, then exit. Does not crawl "
        "or touch Telegram. The scheduler also does this automatically every day at "
        "03:00 (see start_scheduler) — this flag is for on-demand/manual backups.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)

    setup_logging(config.log_path, config.log_level)

    try:
        if args.backup_now:
            run_backup(config)
        elif args.dry_run:
            db = Database(config.db_path, config.timezone)
            run_cycle(db, config, dry_run=True)
        elif args.run_once:
            config.require_telegram()
            db = Database(config.db_path, config.timezone)
            ensure_initial_baseline(db, config)
            run_cycle(db, config, dry_run=False)
        else:
            config.require_telegram()
            db = Database(config.db_path, config.timezone)
            start_scheduler(db, config)
    except RuntimeError as exc:
        logger.error(str(exc))
        print(f"Lỗi cấu hình: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Application-wide logging setup.

Matches the format shown in PROJECT SPEC section 20:
    2026-09-14 10:00:00 INFO  Starting crawl
    2026-09-14 10:00:05 ERROR Vietstock: timeout

One call to setup_logging() configures the root logger with both a
console handler and a rotating file handler under logs/app.log; every
module then just does `logging.getLogger(__name__)`.
"""

import logging
import logging.handlers
from pathlib import Path


def setup_logging(log_path: Path, level: str = "INFO") -> None:
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)-5s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level.upper())

    # Avoid duplicate handlers if setup_logging() is called more than
    # once in the same process (e.g. in tests).
    root.handlers.clear()

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    file_handler = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # These libraries are chatty at INFO/DEBUG; keep our log readable.
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

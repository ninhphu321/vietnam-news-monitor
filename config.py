"""Loads configuration from environment / .env.

Nothing here talks to the network or the database — it just resolves
settings with sane defaults so the rest of the app can import a single
`config` object. Telegram credentials are NOT validated at import time:
--dry-run must work without a .env file, so validation happens once,
right before the app actually tries to send a Telegram message
(see Config.require_telegram()).
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env")


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from None


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Config:
    telegram_bot_token: str = field(default_factory=lambda: os.getenv("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: os.getenv("TELEGRAM_CHAT_ID", ""))

    # Day/night variable crawl cadence (V3, per user request): finance
    # news volume drops overnight, so poll less often then. Day window
    # is [day_start_hour, night_start_hour); night is the rest,
    # wrapping past midnight. Replaces a single fixed interval.
    day_start_hour: int = field(default_factory=lambda: _env_int("DAY_START_HOUR", 6))
    night_start_hour: int = field(default_factory=lambda: _env_int("NIGHT_START_HOUR", 23))
    day_crawl_interval_minutes: int = field(
        default_factory=lambda: _env_int("DAY_CRAWL_INTERVAL_MINUTES", 30)
    )
    night_crawl_interval_minutes: int = field(
        default_factory=lambda: _env_int("NIGHT_CRAWL_INTERVAL_MINUTES", 60)
    )

    request_timeout: int = field(default_factory=lambda: _env_int("REQUEST_TIMEOUT", 15))
    max_retries: int = field(default_factory=lambda: _env_int("MAX_RETRIES", 3))
    initial_scan_send: bool = field(default_factory=lambda: _env_bool("INITIAL_SCAN_SEND", False))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))

    db_path: Path = field(default_factory=lambda: BASE_DIR / "data" / "news.db")
    log_path: Path = field(default_factory=lambda: BASE_DIR / "logs" / "app.log")
    timezone: str = field(default_factory=lambda: os.getenv("TIMEZONE", "Asia/Ho_Chi_Minh"))

    # V3 reliability: flag a source as possibly-broken if it hasn't
    # produced a single new article in this many hours (a feed that
    # still returns HTTP 200 but stopped changing — the real VietnamNet
    # incident — never raises a CrawlerError, so nothing else in the
    # app would ever notice on its own).
    stale_source_hours: int = field(default_factory=lambda: _env_int("STALE_SOURCE_HOURS", 24))
    # Re-alert for the same still-stale source at most this often, so a
    # broken feed doesn't re-notify every single 15-minute cycle.
    stale_alert_cooldown_hours: int = field(
        default_factory=lambda: _env_int("STALE_ALERT_COOLDOWN_HOURS", 24)
    )

    backup_dir: Path = field(default_factory=lambda: BASE_DIR / "backup")
    backup_keep_days: int = field(default_factory=lambda: _env_int("BACKUP_KEEP_DAYS", 14))

    user_agent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 "
        "NewsMonitor/1.0 (+personal news watcher)"
    )

    telegram_message_limit: int = 4096

    def require_telegram(self) -> None:
        """Raise a clear error if Telegram credentials are missing.

        Called only on the send path (never for --dry-run), so a
        developer running --dry-run with an empty .env gets a working
        preview instead of a confusing crash.
        """
        missing = [
            name
            for name, value in (
                ("TELEGRAM_BOT_TOKEN", self.telegram_bot_token),
                ("TELEGRAM_CHAT_ID", self.telegram_chat_id),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing required Telegram config: "
                + ", ".join(missing)
                + ". Copy .env.example to .env and fill these in."
            )


config = Config()

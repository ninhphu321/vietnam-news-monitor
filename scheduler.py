"""Crawl orchestration + the fixed-interval scheduler.

This module owns the flow from PROJECT SPEC section 16:

    crawler -> normalize -> check URL -> insert if new -> telegram -> sent_at

run_cycle() is called both by `main.py --run-once` (once) and by the
APScheduler job below (every N minutes) — there is exactly one code
path for "what happens in a cycle", so manual runs and scheduled runs
can never drift apart.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from backup import backup_database
from config import Config
from core.relevance import drop_reason
from crawlers import CRAWLER_CLASSES
from crawlers.base import CrawlerError
from database import Database
from models import NewsItem
from personal_watchlist import load_personal_watchlist, match_new_articles
import telegram
from web.analytics import daily_stats_rows
from web.brands import load_watchlist
from web.brandwatch import LEVEL_URGENT, crisis_alerts, tag_articles
from web.issues import Issue, top_issues
from web.signals import ACCELERATING, classify_lifecycle, should_alert
from web.source_registry import load_source_registry, weight_for

logger = logging.getLogger(__name__)


CrawlStatus = Dict[str, Tuple[bool, Optional[str]]]


@dataclass
class SnapshotResult:
    """snapshot_data()'s return value: the ranked issues it just
    persisted (unchanged shape from before — still what Telegram's
    top_signals expects, roadmap V2 §19) plus, separately, any issue
    that *just* transitioned into ACCELERATING this cycle while also
    passing web.signals.should_alert()'s bar (roadmap V3 §26)."""

    ranked_issues: List[Tuple[Issue, str]] = field(default_factory=list)
    new_alerts: List[Issue] = field(default_factory=list)


def _build_crawlers(cfg: Config):
    return [
        cls(
            timeout=cfg.request_timeout,
            max_retries=cfg.max_retries,
            user_agent=cfg.user_agent,
        )
        for cls in CRAWLER_CLASSES
    ]


def _drop_non_economic(items: List[NewsItem]) -> Tuple[List[NewsItem], List[Tuple[str, str]]]:
    """Economy-only feed (user request 2026-10): split a crawler's items
    into (kept, [(title, matched social term)]) — see core/relevance.py for
    the rule and why it is conservative. Dropped items never reach the DB
    or Telegram; the names are logged each cycle so a bad drop is visible
    in the Actions log, and the term lists are one file to tune."""
    kept, dropped = [], []
    for item in items:
        reason = drop_reason(item.title)
        if reason:
            dropped.append((item.title, reason))
        else:
            kept.append(item)
    return kept, dropped


def crawl_all(cfg: Config) -> Tuple[Dict[str, List[NewsItem]], CrawlStatus]:
    """Run every crawler, isolating failures per source.

    Returns (items_by_source, status) where status maps
    source_name -> (ok, error_detail). A source that raises never
    takes the rest of the app down (spec section 12: "Crawler của một
    nguồn bị lỗi không được làm crash toàn bộ application").
    """
    items_by_source: Dict[str, List[NewsItem]] = {}
    status: CrawlStatus = {}

    for crawler in _build_crawlers(cfg):
        name = crawler.source_name
        try:
            items = crawler.crawl()
            items, dropped = _drop_non_economic(items)
            items_by_source[name] = items
            status[name] = (True, None)
            logger.info("%s: %d articles found", name, len(items))
            if dropped:
                logger.info(
                    "%s: skipped %d non-economic article(s): %s", name, len(dropped),
                    "; ".join(f"[{reason}] {title[:70]}" for title, reason in dropped[:3]),
                )
        except CrawlerError as exc:
            items_by_source[name] = []
            status[name] = (False, str(exc))
            logger.error("%s: %s", name, exc)
        except Exception as exc:  # noqa: BLE001 - a crawler bug must not crash the app
            items_by_source[name] = []
            status[name] = (False, f"Unexpected error: {exc}")
            logger.exception("%s: unexpected error", name)

    return items_by_source, status


def _sort_for_delivery(items: List[NewsItem]) -> List[NewsItem]:
    """Newest first; items without a timestamp keep their original
    (site-returned) relative order and are appended after every dated
    item. Used only for the --dry-run terminal preview."""
    dated = [i for i in items if i.published_at is not None]
    undated = [i for i in items if i.published_at is None]
    dated.sort(key=lambda i: i.published_at, reverse=True)
    return dated + undated


def _group_pending_by_source(pending: List[NewsItem]) -> Dict[str, List[NewsItem]]:
    """Group not-yet-sent articles by source, preserving the configured
    crawler order (spec section 12: "giữ thứ tự cấu hình", never a
    global time sort) and dropping sources with nothing pending.
    Within a source, articles are oldest-first (spec example: 10:03
    before 10:11)."""
    grouped: Dict[str, List[NewsItem]] = {cls.source_name: [] for cls in CRAWLER_CLASSES}
    for item in pending:
        grouped.setdefault(item.source, []).append(item)

    for source, items in grouped.items():
        dated = sorted((i for i in items if i.published_at is not None), key=lambda i: i.published_at)
        undated = [i for i in items if i.published_at is None]
        grouped[source] = dated + undated

    return {source: items for source, items in grouped.items() if items}


def ensure_initial_baseline(db: Database, cfg: Config) -> None:
    """First-run behavior from spec section 7, extended (V2) to also
    cover sources added after the very first deploy.

    Whole-DB-empty case (fresh deploy): if INITIAL_SCAN_SEND=false
    (default), crawl once, record every article found as already-seen
    baseline (initial_seen=1), send nothing to Telegram. If
    INITIAL_SCAN_SEND=true, this is a no-op: the first real cycle runs
    normally and sends everything it finds, by design.

    New-source case (V2): the database already has history (V1 was
    running), but one or more crawlers in CRAWLER_CLASSES have never
    contributed a row (e.g. a source added by this upgrade). Without
    this, that source's entire current article list would look "new"
    on the very next real cycle and flood Telegram in one batch (spec
    section 9's anti-flood rule applies here too, not just to a fully
    fresh deploy). So any such source is silently baseline-seeded the
    same way, regardless of INITIAL_SCAN_SEND — that flag is about the
    first-ever deploy, not about re-flooding an already-running chat
    every time a source is added.

    Either way, a source that fails during baseline seeding is simply
    skipped for seeding — its articles will be treated as "new" on the
    next real cycle and sent then, which is logged clearly rather than
    silently swallowed.
    """
    db_is_empty = db.is_empty()
    if db_is_empty and cfg.initial_scan_send:
        logger.info(
            "First run detected, INITIAL_SCAN_SEND=true -> skipping baseline "
            "seeding, first cycle will send all current articles."
        )
        return

    known_sources = db.known_sources()
    new_sources = {cls.source_name for cls in CRAWLER_CLASSES} - known_sources
    if not new_sources:
        return

    if db_is_empty:
        logger.info("First run detected, INITIAL_SCAN_SEND=false -> seeding baseline (no Telegram send).")
    else:
        logger.info(
            "New source(s) detected with no history yet: %s -> seeding baseline "
            "for them only (no Telegram send).",
            ", ".join(sorted(new_sources)),
        )

    items_by_source, status = crawl_all(cfg)
    seeded = 0
    for name, items in items_by_source.items():
        if name not in new_sources:
            continue
        ok, _ = status[name]
        if not ok:
            logger.warning(
                "%s failed during baseline seeding; its articles will be sent as "
                "new on the next cycle instead of being seeded.",
                name,
            )
            continue
        for item in items:
            if db.insert_if_new(item, initial_seen=True):
                seeded += 1
    logger.info("Baseline seeding complete: %d article(s) marked initial_seen.", seeded)


def _detect_stale_sources(
    db: Database, cfg: Config, status: CrawlStatus, now: datetime
) -> List[Tuple[str, datetime]]:
    """V3 reliability check: flag a source whose feed has gone silently
    stale — still crawls "successfully" (no CrawlerError) but hasn't
    produced a single genuinely new article in `cfg.stale_source_hours`
    (the real VietnamNet incident: HTTP 200 forever, content frozen —
    the normal error-report path never catches this since nothing ever
    raises). Only sources that crawled OK this cycle are checked; an
    already-failing source is already visible via the error report.

    Returns (source, last_new_article_at) pairs to warn about this
    cycle — newly-stale, or past their re-alert cooldown — and updates
    source_health bookkeeping (including clearing a source that has
    recovered) as a side effect.
    """
    to_alert: List[Tuple[str, datetime]] = []
    threshold = timedelta(hours=cfg.stale_source_hours)
    cooldown = timedelta(hours=cfg.stale_alert_cooldown_hours)

    for name, (ok, _detail) in status.items():
        if not ok:
            continue
        last_new = db.last_new_article_at(name)
        if last_new is None:
            continue  # brand new source, still baselining — nothing to compare yet

        if now - last_new <= threshold:
            if db.get_stale_alert(name) is not None:
                db.clear_stale_alert(name)  # recovered
            continue

        last_alert = db.get_stale_alert(name)
        if last_alert is not None and now - last_alert < cooldown:
            continue  # already alerted recently; stay quiet until cooldown passes

        db.set_stale_alert(name, now)
        to_alert.append((name, last_new))

    return to_alert


def run_backup(cfg: Config) -> None:
    """Scheduled daily job (see start_scheduler): timestamped copy of
    the SQLite database + pruning backups older than
    cfg.backup_keep_days. Best-effort — a backup failure is logged but
    must never take down the crawl/Telegram scheduler."""
    try:
        backup_database(cfg.db_path, cfg.backup_dir, cfg.backup_keep_days, cfg.timezone)
    except OSError as exc:
        logger.error("Database backup failed: %s", exc)


STATS_REFRESH_DAYS = 3


def snapshot_data(
    db: Database, now: datetime, cfg: Optional[Config] = None
) -> Optional[SnapshotResult]:
    """Persist derived data that would otherwise be lost or recomputed
    from scratch: today's Top Issues (-> issue_history, plus signal
    lifecycle transitions -> signal_events) and per-day source/topic
    counts (-> daily_stats). Runs in the crawl job — NOT in the site
    build — because the CI workflow pushes news.db to the db-state
    branch *before* it builds the site; anything written during the
    build would never be saved. Best-effort: a failure here is logged
    and must never affect crawling or Telegram delivery.

    `cfg` is optional (defaults to every source at equal weight) only so
    existing callers/tests that predate SignalScore's Source Weight
    component keep working without passing one.

    Returns a SnapshotResult (ranked issues for Telegram's "TOP SIGNALS"
    section, roadmap V2 §19, plus any new Signal Alert per roadmap V3
    §26) — already computed here, so run_cycle() reuses both instead of
    recomputing top_issues() a second time — or None if the snapshot
    itself failed, so a broken signal computation degrades Telegram to
    "no top signals section, no alerts" rather than taking the whole
    cycle down."""
    try:
        articles = db.get_all_articles()
        today = now.date().isoformat()

        registry = load_source_registry(cfg.source_registry_path) if cfg else {}
        source_weights = {a["source"]: weight_for(a["source"], registry) for a in articles}
        issues = top_issues(articles, now, source_weights=source_weights)

        # Roadmap V2 §15-16: classify each issue's lifecycle by comparing
        # this cycle's velocity to whatever was already on record for it
        # today (None if this is its first cycle appearing) — fetched
        # BEFORE the upsert below overwrites it — and log every actual
        # transition to signal_events so "why is this ACCELERATING" stays
        # answerable later, not just the latest snapshot.
        previous_by_id = {row["issue_id"]: row for row in db.get_issue_history(since_day=today)}
        issue_rows = []
        ranked: List[Tuple[Issue, str]] = []
        new_alerts: List[Issue] = []
        for rank, i in enumerate(issues, start=1):
            previous = previous_by_id.get(i.issue_id)
            previous_velocity = previous["velocity"] if previous else None
            status = classify_lifecycle(i.velocity, previous_velocity)
            previous_status = previous["signal_status"] if previous else None
            if status != previous_status:
                db.record_signal_event(
                    today, i.issue_id, previous_status, status,
                    i.velocity, i.article_count, i.unique_source_count, now,
                )
                # Roadmap V3 §26: a real (not every-cycle) transition
                # into ACCELERATING is exactly what naturally rate-
                # limits Signal Alerts — an issue that stays
                # ACCELERATING for several consecutive cycles doesn't
                # re-alert until it cools down and re-accelerates.
                min_sources = cfg.signal_alert_min_sources if cfg else None
                min_score = cfg.signal_alert_min_score if cfg else None
                alert_kwargs = {}
                if min_sources is not None:
                    alert_kwargs["min_sources"] = min_sources
                if min_score is not None:
                    alert_kwargs["min_score"] = min_score
                if status == ACCELERATING and should_alert(i.unique_source_count, i.hot_score, **alert_kwargs):
                    new_alerts.append(i)
            issue_rows.append({
                "issue_id": i.issue_id, "title": i.issue_title, "rank": rank,
                "hot_score": i.hot_score, "article_count": i.article_count,
                "source_count": i.unique_source_count,
                "first_seen_at": i.first_seen_at.isoformat(), "last_seen_at": i.last_seen_at.isoformat(),
                "velocity": i.velocity, "signal_status": status,
            })
            ranked.append((i, status))
        db.record_issues(today, issue_rows, now)

        # First run on an existing DB backfills every historical day; after
        # that only the last few days are recomputed (older days are final).
        if db.daily_stats_is_empty():
            only_days = None
        else:
            only_days = {(now - timedelta(days=d)).date() for d in range(STATS_REFRESH_DAYS)}
        rows = daily_stats_rows(articles, only_days)
        days = only_days if only_days is not None else {date.fromisoformat(r[0]) for r in rows}
        db.replace_daily_stats([d.isoformat() for d in days], rows)
        return SnapshotResult(ranked_issues=ranked, new_alerts=new_alerts)
    except Exception:  # noqa: BLE001 - secondary feature, see docstring
        logger.exception("Data snapshot (issue_history/daily_stats) failed; continuing.")
        return None


def check_crisis(db: Database, cfg: Config, now: datetime) -> None:
    """Page (via Telegram) when strong-negative headlines about one brand
    appear in >= cfg.crisis_min_sources outlets within
    cfg.crisis_window_minutes. One alert per brand per cooldown window;
    an "urgent" alert may override the cooldown of an earlier "escalating"
    one. Best-effort like the other secondary checks: never raises."""
    try:
        index, watch = load_watchlist(cfg.watchlist_path)
        tagged = tag_articles(db.get_all_articles(), index, watch)
        alerts = crisis_alerts(
            tagged, now, watch, index,
            window_minutes=cfg.crisis_window_minutes, min_sources=cfg.crisis_min_sources,
        )
        for alert in alerts:
            last = db.get_crisis_alert(alert.brand)
            if last is not None:
                last_level, last_at = last
                cooling = now - last_at < timedelta(hours=cfg.crisis_cooldown_hours)
                upgraded = alert.level == LEVEL_URGENT and last_level != LEVEL_URGENT
                if cooling and not upgraded:
                    continue
            try:
                telegram.send_message(
                    cfg.telegram_bot_token, cfg.telegram_chat_id,
                    telegram.format_crisis_alert(alert, now),
                    cfg.request_timeout, cfg.max_retries,
                )
            except telegram.TelegramError as exc:
                logger.error("Failed to send crisis alert for %s: %s", alert.brand, exc)
                continue
            db.set_crisis_alert(alert.brand, alert.level, now)
            logger.warning("Crisis alert sent: %s (%s, %d outlet(s))", alert.brand, alert.level, len(alert.sources))
    except Exception:  # noqa: BLE001 - secondary feature, see docstring
        logger.exception("Crisis check failed; continuing.")


def send_signal_alerts(cfg: Config, now: datetime, alerts: List[Issue]) -> None:
    """Roadmap V3 §26: one dedicated Telegram message per issue in
    `alerts` (already filtered by snapshot_data() to "just transitioned
    to ACCELERATING this cycle AND passes web.signals.should_alert()")
    — distinct from the "TOP TÍN HIỆU" section that already leads every
    regular digest regardless of any threshold. Best-effort like
    check_crisis(): a failed send is logged and must never affect the
    primary digest that already went out earlier in run_cycle()."""
    try:
        for issue in alerts:
            try:
                telegram.send_message(
                    cfg.telegram_bot_token, cfg.telegram_chat_id,
                    telegram.format_signal_alert(issue, now),
                    cfg.request_timeout, cfg.max_retries,
                )
            except telegram.TelegramError as exc:
                logger.error("Failed to send signal alert for %s: %s", issue.issue_id, exc)
                continue
            logger.warning(
                "Signal alert sent: %s (%d bài, %d nguồn, HOT %.0f)",
                issue.issue_id, issue.article_count, issue.unique_source_count, issue.hot_score,
            )
    except Exception:  # noqa: BLE001 - secondary feature, see docstring
        logger.exception("Signal alert dispatch failed; continuing.")


def send_personal_watchlist_alert(cfg: Config, now: datetime, newly_inserted: List[NewsItem]) -> None:
    """Roadmap V4 §29-34 "My Watchlist" — private, local-only, Telegram-
    only (see personal_watchlist.py's module docstring for why there is
    no public website page for this). A no-op when
    cfg.personal_watchlist_path doesn't exist, so leaving the feature
    unconfigured costs nothing every cycle beyond a file-existence
    check. Best-effort like check_crisis()/send_signal_alerts(): a
    failure here must never affect the primary digest."""
    try:
        index = load_personal_watchlist(cfg.personal_watchlist_path)
        if index is None:
            return
        matches = match_new_articles(index, newly_inserted)
        if not matches:
            return
        telegram.send_message(
            cfg.telegram_bot_token, cfg.telegram_chat_id,
            telegram.format_personal_watchlist_alert(matches, now),
            cfg.request_timeout, cfg.max_retries,
        )
        logger.info("Personal watchlist alert sent: %s", [m.entity for m in matches])
    except telegram.TelegramError as exc:
        logger.error("Failed to send personal watchlist alert: %s", exc)
    except Exception:  # noqa: BLE001 - secondary feature, see docstring
        logger.exception("Personal watchlist check failed; continuing.")


def run_cycle(db: Database, cfg: Config, dry_run: bool = False) -> None:
    tz = ZoneInfo(cfg.timezone)
    now = datetime.now(tz)
    logger.info("Starting crawl")

    items_by_source, status = crawl_all(cfg)
    all_crawled = [item for items in items_by_source.values() for item in items]

    if dry_run:
        _print_dry_run(items_by_source, status, db)
        return

    # Insert new articles first (spec section 16 flow), BEFORE attempting
    # any Telegram send, so a crash or a Telegram outage can never lose
    # an article: it will simply still have sent_at = NULL and be
    # retried next cycle via get_pending().
    newly_inserted: List[NewsItem] = []
    for item in all_crawled:
        if db.insert_if_new(item):
            newly_inserted.append(item)

    snapshot_result = snapshot_data(db, now, cfg)
    top_signals = snapshot_result.ranked_issues if snapshot_result else None

    # get_pending() already includes rows from this cycle's inserts (they
    # were just written with sent_at NULL), so it's the single source of
    # truth for "what to try sending now" — this also means articles from
    # a source that failed to crawl or send last cycle are retried here
    # even if this cycle's crawl of that source also failed.
    grouped = _group_pending_by_source(db.get_pending())

    logger.info("New articles: %d", len(newly_inserted))

    errored_sources = [name for name, (ok, _detail) in status.items() if not ok]
    any_error = bool(errored_sources)
    all_error = bool(status) and len(errored_sources) == len(status)

    sent_urls: List[str] = []
    try:
        if grouped:
            # Spec section 15: one batch per cycle; only split on length.
            messages = telegram.format_grouped_articles(
                grouped,
                limit=cfg.telegram_message_limit,
                errored_sources=errored_sources or None,
                top_signals=top_signals,
            )
            telegram.send_messages(
                cfg.telegram_bot_token, cfg.telegram_chat_id, messages,
                cfg.request_timeout, cfg.max_retries,
            )
            sent_urls = [i.url for items in grouped.values() for i in items]
            logger.info(
                "Telegram message sent (%d article(s) across %d source(s), %d message part(s)).",
                len(sent_urls), len(grouped), len(messages),
            )
        elif all_error:
            # Spec section 14: never let a fully-failed cycle look like
            # "no new articles".
            text = telegram.format_all_sources_failed(errored_sources, now)
            telegram.send_message(
                cfg.telegram_bot_token, cfg.telegram_chat_id, text,
                cfg.request_timeout, cfg.max_retries,
            )
            logger.info("Telegram 'all sources failed' notice sent.")
        elif any_error:
            text = telegram.format_partial_failure_no_new(errored_sources, now)
            telegram.send_message(
                cfg.telegram_bot_token, cfg.telegram_chat_id, text,
                cfg.request_timeout, cfg.max_retries,
            )
            logger.info("Telegram partial-failure notice sent.")
        else:
            text = telegram.format_no_new_articles(now)
            telegram.send_message(
                cfg.telegram_bot_token, cfg.telegram_chat_id, text,
                cfg.request_timeout, cfg.max_retries,
            )
            logger.info("Telegram 'no new articles' notice sent.")
    except telegram.TelegramError as exc:
        # Crawl succeeded; Telegram did not. Do NOT mark anything as
        # sent - spec section 16/17: "crawl thành công != telegram gửi
        # thành công". Everything in `grouped` stays sent_at=NULL and
        # will be retried next cycle.
        logger.error("Telegram delivery failed this cycle: %s", exc)
        return

    if sent_urls:
        db.mark_sent(sent_urls, sent_at=now)

    check_crisis(db, cfg, now)
    send_signal_alerts(cfg, now, snapshot_result.new_alerts if snapshot_result else [])
    send_personal_watchlist_alert(cfg, now, newly_inserted)

    # Best-effort, secondary check — must never affect the primary
    # crawl/send outcome above, success or failure.
    stale = _detect_stale_sources(db, cfg, status, now)
    if stale:
        try:
            text = telegram.format_stale_sources_warning(stale, cfg.stale_source_hours, now)
            telegram.send_message(
                cfg.telegram_bot_token, cfg.telegram_chat_id, text,
                cfg.request_timeout, cfg.max_retries,
            )
            logger.warning("Stale source(s) detected and alerted: %s", ", ".join(s for s, _ in stale))
        except telegram.TelegramError as exc:
            logger.error("Failed to send stale-source warning: %s", exc)


def _print_dry_run(items_by_source, status, db: Database) -> None:
    """Dry run per spec section 22: crawl, parse, check duplicate,
    print to terminal, NEVER touch the database or Telegram."""
    print()
    for source, items in items_by_source.items():
        ok, detail = status[source]
        print(f"[{source}]")
        if not ok:
            print(f"  ERROR: {detail}")
            print()
            continue
        new_items = [i for i in items if not db.url_exists(i.url)]
        if not new_items:
            print("  (không có bài mới)")
        for item in _sort_for_delivery(new_items):
            t = item.published_at.strftime("%d/%m %H:%M") if item.published_at else "--/-- --:--"
            print(f"  {t} | {item.title}")
            print(f"       {item.url}")
        print()


def _minute_expr(interval_minutes: int) -> str:
    """APScheduler/cron minute field for firing every `interval_minutes`
    within an hour. >=60 collapses to "once per hour, on the hour";
    an interval that doesn't evenly divide 60 also falls back to that
    (there is no clean "every 30 minutes" for e.g. 40) rather than
    silently firing at the wrong cadence."""
    if interval_minutes >= 60 or 60 % interval_minutes != 0:
        return "0"
    return f"*/{interval_minutes}"


def start_scheduler(db: Database, cfg: Config) -> None:
    ensure_initial_baseline(db, cfg)

    scheduler = BlockingScheduler(timezone=cfg.timezone)
    now = datetime.now(ZoneInfo(cfg.timezone))

    scheduler.add_job(
        run_cycle,
        trigger=CronTrigger(minute=_minute_expr(cfg.crawl_interval_minutes), timezone=cfg.timezone),
        kwargs={"db": db, "cfg": cfg, "dry_run": False},
        id="crawl_cycle",
        max_instances=1,
        coalesce=True,
        next_run_time=now,  # fire once immediately on startup, then follow the cron cadence
    )

    # V3 reliability: daily SQLite backup, independent of the crawl
    # cycle's own schedule so it survives even if the interval changes.
    scheduler.add_job(
        run_backup,
        trigger=CronTrigger(hour=3, minute=0, timezone=cfg.timezone),
        kwargs={"cfg": cfg},
        id="daily_backup",
        max_instances=1,
        coalesce=True,
    )

    logger.info("Scheduler started: every %d minute(s), around the clock.", cfg.crawl_interval_minutes)
    logger.info("Daily backup scheduled: 03:00 (%s), keeping %d day(s).", cfg.timezone, cfg.backup_keep_days)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Scheduler stopped.")

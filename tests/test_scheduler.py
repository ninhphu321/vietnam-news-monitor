from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import scheduler
import telegram
from config import Config
from crawlers.base import CrawlerError
from models import NewsItem

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def make_cfg(**overrides):
    defaults = dict(
        telegram_bot_token="t",
        telegram_chat_id="c",
        request_timeout=1,
        max_retries=1,
        initial_scan_send=False,
        log_level="INFO",
    )
    defaults.update(overrides)
    return Config(**defaults)


class FakeCrawler:
    def __init__(self, source_name, items=None, error=None, **_kwargs):
        self.source_name = source_name
        self.source_url = f"https://example.com/{source_name}"
        self._items = items or []
        self._error = error

    def crawl(self):
        if self._error:
            raise self._error
        return self._items


def fake_crawler_factory(name, items=None, error=None):
    def _factory(**kwargs):
        return FakeCrawler(name, items=items, error=error)

    _factory.source_name = name
    return _factory


def test_crawl_all_isolates_per_source_failures(monkeypatch):
    ok_items = [NewsItem("A", "t", "https://x/1", datetime.now(TZ))]
    monkeypatch.setattr(
        scheduler,
        "CRAWLER_CLASSES",
        [
            fake_crawler_factory("A", items=ok_items),
            fake_crawler_factory("B", error=CrawlerError("boom")),
            fake_crawler_factory("C", error=RuntimeError("unexpected bug")),
        ],
    )
    cfg = make_cfg()
    items_by_source, status = scheduler.crawl_all(cfg)

    assert status["A"] == (True, None)
    assert status["B"][0] is False and "boom" in status["B"][1]
    assert status["C"][0] is False  # unexpected exceptions don't crash the app either
    assert items_by_source["A"] == ok_items
    assert items_by_source["B"] == []
    assert items_by_source["C"] == []


def test_run_cycle_sends_digest_and_marks_sent(db, monkeypatch):
    items = [
        NewsItem("A", "Tiêu đề 1", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ)),
        NewsItem("A", "Tiêu đề 2", "https://x/2", datetime(2026, 9, 14, 9, 0, tzinfo=TZ)),
    ]
    monkeypatch.setattr(scheduler, "CRAWLER_CLASSES", [fake_crawler_factory("A", items=items)])

    sent_calls = []
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: sent_calls.append(("single", a)))
    monkeypatch.setattr(telegram, "send_messages", lambda *a, **k: sent_calls.append(("batch", a)))

    cfg = make_cfg()
    scheduler.run_cycle(db, cfg, dry_run=False)

    assert db.count_all() == 2
    assert db.get_pending() == []  # both marked sent
    assert any(kind == "batch" for kind, _ in sent_calls)
    assert not any(kind == "single" for kind, _ in sent_calls)  # no error, no "no-new" needed


def test_run_cycle_sends_all_failed_report_when_every_source_fails(db, monkeypatch):
    monkeypatch.setattr(
        scheduler, "CRAWLER_CLASSES", [fake_crawler_factory("A", error=CrawlerError("timeout"))]
    )
    sent_calls = []
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: sent_calls.append(a[2]))
    monkeypatch.setattr(telegram, "send_messages", lambda *a, **k: sent_calls.append(a))

    cfg = make_cfg()
    scheduler.run_cycle(db, cfg, dry_run=False)

    assert any("Không thể hoàn tất lượt quét" in text for text in sent_calls if isinstance(text, str))


def test_run_cycle_appends_error_footer_when_new_articles_and_partial_failure(db, monkeypatch):
    items = [NewsItem("A", "Tiêu đề", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ))]
    monkeypatch.setattr(
        scheduler,
        "CRAWLER_CLASSES",
        [
            fake_crawler_factory("A", items=items),
            fake_crawler_factory("B", error=CrawlerError("timeout")),
        ],
    )
    sent_calls = []
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: sent_calls.append(a[2]))
    monkeypatch.setattr(telegram, "send_messages", lambda *a, **k: sent_calls.append(a[2]))

    cfg = make_cfg()
    scheduler.run_cycle(db, cfg, dry_run=False)

    # Spec section 14/15: errors + new articles from other sources must
    # land in the SAME batch, never a separate "no new" message.
    assert len(sent_calls) == 1
    (messages,) = sent_calls
    assert any("⚠️ Nguồn lỗi: B" in msg for msg in messages)
    assert any("<b>A</b>" in msg for msg in messages)


def test_run_cycle_partial_failure_with_no_new_articles_stays_visible(db, monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "CRAWLER_CLASSES",
        [fake_crawler_factory("A", items=[]), fake_crawler_factory("B", error=CrawlerError("timeout"))],
    )
    sent_calls = []
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: sent_calls.append(a[2]))
    monkeypatch.setattr(telegram, "send_messages", lambda *a, **k: sent_calls.append(a))

    cfg = make_cfg()
    scheduler.run_cycle(db, cfg, dry_run=False)

    assert any("⚠️ <b>NEWS MONITOR</b>" in text for text in sent_calls if isinstance(text, str))
    assert not any("🟢" in text for text in sent_calls if isinstance(text, str))


def test_run_cycle_does_not_mark_sent_when_telegram_fails(db, monkeypatch):
    items = [NewsItem("A", "T", "https://x/1", datetime.now(TZ))]
    monkeypatch.setattr(scheduler, "CRAWLER_CLASSES", [fake_crawler_factory("A", items=items)])

    def failing_send_messages(*a, **k):
        raise telegram.TelegramError("network down")

    monkeypatch.setattr(telegram, "send_messages", failing_send_messages)
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: None)

    cfg = make_cfg()
    scheduler.run_cycle(db, cfg, dry_run=False)

    # Article was still recorded (no data loss) but not marked sent.
    assert db.count_all() == 1
    assert len(db.get_pending()) == 1


def test_run_cycle_dry_run_never_touches_db_or_telegram(db, monkeypatch, capsys):
    items = [NewsItem("A", "T", "https://x/1", datetime.now(TZ))]
    monkeypatch.setattr(scheduler, "CRAWLER_CLASSES", [fake_crawler_factory("A", items=items)])

    called = []
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: called.append(1))
    monkeypatch.setattr(telegram, "send_messages", lambda *a, **k: called.append(1))

    cfg = make_cfg()
    scheduler.run_cycle(db, cfg, dry_run=True)

    assert db.is_empty() is True
    assert called == []
    out = capsys.readouterr().out
    assert "[A]" in out


def test_ensure_initial_baseline_seeds_without_sending(db, monkeypatch):
    items = [
        NewsItem("A", "Bài cũ 1", "https://x/1", datetime.now(TZ)),
        NewsItem("A", "Bài cũ 2", "https://x/2", datetime.now(TZ)),
    ]
    monkeypatch.setattr(scheduler, "CRAWLER_CLASSES", [fake_crawler_factory("A", items=items)])

    called = []
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: called.append(1))
    monkeypatch.setattr(telegram, "send_messages", lambda *a, **k: called.append(1))

    cfg = make_cfg(initial_scan_send=False)
    scheduler.ensure_initial_baseline(db, cfg)

    assert db.count_all() == 2
    assert db.get_pending() == []  # seeded as initial_seen, not "pending to send"
    assert called == []


def test_ensure_initial_baseline_noop_when_db_not_empty(db, monkeypatch):
    db.insert_if_new(NewsItem("A", "existing", "https://x/existing", datetime.now(TZ)))
    monkeypatch.setattr(
        scheduler,
        "CRAWLER_CLASSES",
        [fake_crawler_factory("A", items=[NewsItem("A", "new", "https://x/new", datetime.now(TZ))])],
    )
    cfg = make_cfg()
    scheduler.ensure_initial_baseline(db, cfg)
    # Should not have crawled/seeded again.
    assert db.count_all() == 1


def test_ensure_initial_baseline_seeds_only_a_newly_added_source(db, monkeypatch):
    """A source added to CRAWLER_CLASSES after V1 already has history
    (e.g. this V2 upgrade) must be baseline-seeded on its own, without
    touching an already-known source's pending state — otherwise its
    whole current article list floods Telegram as "new" next cycle."""
    db.insert_if_new(NewsItem("A", "existing A", "https://x/a-existing", datetime.now(TZ)))
    monkeypatch.setattr(
        scheduler,
        "CRAWLER_CLASSES",
        [
            fake_crawler_factory("A", items=[NewsItem("A", "a-new", "https://x/a-new", datetime.now(TZ))]),
            fake_crawler_factory(
                "B", items=[NewsItem("B", "b1", "https://x/b1", datetime.now(TZ)),
                            NewsItem("B", "b2", "https://x/b2", datetime.now(TZ))]
            ),
        ],
    )
    cfg = make_cfg()
    scheduler.ensure_initial_baseline(db, cfg)

    # Source A (already known) is untouched: its crawled "a-new" article
    # was NOT inserted/seeded by baseline logic.
    assert db.count_all() == 3  # 1 pre-existing A + 2 seeded B
    pending = db.get_pending()
    assert [i.source for i in pending] == ["A"]
    assert pending[0].title == "existing A"

    # Source B (brand new) is fully seeded as initial_seen, not pending.
    assert not any(i.source == "B" for i in pending)


def test_sort_for_delivery_puts_dated_desc_before_undated():
    items = [
        NewsItem("A", "old", "u1", datetime(2026, 9, 14, 9, 0, tzinfo=TZ)),
        NewsItem("A", "undated", "u2", None),
        NewsItem("A", "new", "u3", datetime(2026, 9, 14, 10, 0, tzinfo=TZ)),
    ]
    result = scheduler._sort_for_delivery(items)
    assert [i.title for i in result] == ["new", "old", "undated"]


def _backdate_first_seen_at(db, url, when):
    """Test helper: insert_if_new() always stamps first_seen_at with the
    real wall-clock time (by design — see database.py), so simulating
    "this source's last new article was N hours ago" needs a direct
    write instead of controlling it through the public API."""
    with db._connect() as conn:
        conn.execute("UPDATE news SET first_seen_at = ? WHERE url = ?", (when.isoformat(), url))


def test_detect_stale_sources_flags_source_past_threshold(db):
    old = datetime(2026, 8, 8, 10, 0, tzinfo=TZ)  # >1 month before "now" below
    db.insert_if_new(NewsItem("VietnamNet", "old", "https://x/1", old))
    _backdate_first_seen_at(db, "https://x/1", old)

    now = datetime(2026, 9, 14, 20, 0, tzinfo=TZ)
    cfg = make_cfg(stale_source_hours=24, stale_alert_cooldown_hours=24)
    status = {"VietnamNet": (True, None)}

    stale = scheduler._detect_stale_sources(db, cfg, status, now)

    assert stale == [("VietnamNet", old)]
    assert db.get_stale_alert("VietnamNet") == now  # bookkeeping recorded


def test_detect_stale_sources_skips_failed_sources():
    """An already-failing source is visible via the error report;
    double-reporting it as 'stale' too would be noise."""
    status = {"VnExpress": (False, "timeout")}
    cfg = make_cfg()
    stale = scheduler._detect_stale_sources(None, cfg, status, datetime.now(TZ))
    assert stale == []


def test_detect_stale_sources_respects_cooldown(db):
    old = datetime(2026, 8, 8, 10, 0, tzinfo=TZ)
    db.insert_if_new(NewsItem("VietnamNet", "old", "https://x/1", old))
    _backdate_first_seen_at(db, "https://x/1", old)
    cfg = make_cfg(stale_source_hours=24, stale_alert_cooldown_hours=24)
    status = {"VietnamNet": (True, None)}

    first_alert_time = datetime(2026, 9, 14, 20, 0, tzinfo=TZ)
    assert scheduler._detect_stale_sources(db, cfg, status, first_alert_time) == [("VietnamNet", old)]

    # 1 hour later, still within the 24h cooldown -> must not re-alert.
    soon_after = datetime(2026, 9, 14, 21, 0, tzinfo=TZ)
    assert scheduler._detect_stale_sources(db, cfg, status, soon_after) == []

    # Past the cooldown window -> alerts again.
    next_day = datetime(2026, 9, 16, 0, 0, tzinfo=TZ)
    assert scheduler._detect_stale_sources(db, cfg, status, next_day) == [("VietnamNet", old)]


def test_detect_stale_sources_clears_alert_once_recovered(db):
    old = datetime(2026, 8, 8, 10, 0, tzinfo=TZ)
    db.insert_if_new(NewsItem("VietnamNet", "old", "https://x/1", old))
    _backdate_first_seen_at(db, "https://x/1", old)
    cfg = make_cfg(stale_source_hours=24, stale_alert_cooldown_hours=24)
    status = {"VietnamNet": (True, None)}
    now = datetime(2026, 9, 14, 20, 0, tzinfo=TZ)

    scheduler._detect_stale_sources(db, cfg, status, now)
    assert db.get_stale_alert("VietnamNet") is not None

    # Source starts publishing again (fresh row, real insert time -> "now").
    db.insert_if_new(NewsItem("VietnamNet", "fresh", "https://x/2", now))
    scheduler._detect_stale_sources(db, cfg, status, now)
    assert db.get_stale_alert("VietnamNet") is None


def test_time_windowed_cron_kwargs_matches_default_day_night_split():
    """Spec: 06:00-23:00 -> every 15 min, 23:00-06:00 -> every 30 min."""
    cfg = make_cfg()  # day_start_hour=6, night_start_hour=23 by default
    day_kwargs, night_kwargs = scheduler._time_windowed_cron_kwargs(cfg)

    assert day_kwargs == {"hour": "6-22", "minute": "*/15"}
    assert night_kwargs == {"hour": "23,0-5", "minute": "*/30"}


def test_time_windowed_cron_kwargs_respects_custom_boundaries():
    cfg = make_cfg(
        day_start_hour=8, night_start_hour=20,
        day_crawl_interval_minutes=15, night_crawl_interval_minutes=60,
    )
    day_kwargs, night_kwargs = scheduler._time_windowed_cron_kwargs(cfg)

    assert day_kwargs == {"hour": "8-19", "minute": "*/15"}
    assert night_kwargs == {"hour": "20-23,0-7", "minute": "0"}


@pytest.mark.parametrize(
    "hour,expected_night",
    [
        (5, True),   # 05:00 -> still last hour of the night window
        (6, False),  # 06:00 -> day window starts exactly here
        (12, False), # midday -> clearly day
        (22, False), # 22:00 -> last hour of the day window
        (23, True),  # 23:00 -> night window starts exactly here
        (0, True),   # midnight -> night (wrapped past 24h)
    ],
)
def test_is_night_matches_the_configured_window_boundaries(hour, expected_night):
    """Regression guard for the exact 'does the article's crawl hour
    fall in the window it should' boundary check the user asked for —
    off-by-one here would either double-fire or skip a hour at 06:00
    or 23:00."""
    cfg = make_cfg()  # day_start_hour=6, night_start_hour=23
    assert scheduler._is_night(hour, cfg) is expected_night


def test_minute_expr_falls_back_to_once_per_hour_for_non_divisors():
    assert scheduler._minute_expr(30) == "*/30"
    assert scheduler._minute_expr(60) == "0"
    assert scheduler._minute_expr(90) == "0"  # >=60
    assert scheduler._minute_expr(40) == "0"  # doesn't evenly divide 60


def test_day_and_night_crontriggers_actually_fire_at_the_right_times():
    """End-to-end check (not just the cron-string kwargs) that the real
    APScheduler CronTrigger built from them fires article crawls
    exactly inside the window it belongs to — the concrete "does the
    time it actually runs match the window it's supposed to" check."""
    from apscheduler.triggers.cron import CronTrigger

    cfg = make_cfg()
    day_kwargs, night_kwargs = scheduler._time_windowed_cron_kwargs(cfg)
    day_trigger = CronTrigger(timezone=TZ, **day_kwargs)
    night_trigger = CronTrigger(timezone=TZ, **night_kwargs)

    # Day trigger: every 15 min from 06:00, last fire at 22:45, then
    # nothing more until 06:00 the next day (never strays into night).
    after_2244 = datetime(2026, 9, 14, 22, 44, tzinfo=TZ)
    next_day_fire = day_trigger.get_next_fire_time(None, after_2244)
    assert next_day_fire == datetime(2026, 9, 14, 22, 45, tzinfo=TZ)

    after_2245 = datetime(2026, 9, 14, 22, 45, 1, tzinfo=TZ)
    next_day_fire_2 = day_trigger.get_next_fire_time(None, after_2245)
    assert next_day_fire_2 == datetime(2026, 9, 15, 6, 0, tzinfo=TZ)

    # Night trigger: every 30 min starting exactly at 23:00, then
    # 23:30, 00:00..., never fires during the 06:00-22:59 day window.
    after_2259 = datetime(2026, 9, 14, 22, 59, tzinfo=TZ)
    next_night_fire = night_trigger.get_next_fire_time(None, after_2259)
    assert next_night_fire == datetime(2026, 9, 14, 23, 0, tzinfo=TZ)

    after_2300 = datetime(2026, 9, 14, 23, 0, 1, tzinfo=TZ)
    next_night_fire_2 = night_trigger.get_next_fire_time(None, after_2300)
    assert next_night_fire_2 == datetime(2026, 9, 14, 23, 30, tzinfo=TZ)

    after_0530 = datetime(2026, 9, 15, 5, 30, 1, tzinfo=TZ)
    next_night_fire_3 = night_trigger.get_next_fire_time(None, after_0530)
    assert next_night_fire_3 == datetime(2026, 9, 15, 23, 0, tzinfo=TZ)  # skips straight past the whole day


def test_group_pending_by_source_preserves_config_order_and_drops_empty(monkeypatch):
    monkeypatch.setattr(
        scheduler,
        "CRAWLER_CLASSES",
        [fake_crawler_factory("Vietstock"), fake_crawler_factory("Tuổi Trẻ"), fake_crawler_factory("VnExpress")],
    )
    pending = [
        # VnExpress (configured last) appears first in the input list but
        # must still be grouped/ordered by configured source order.
        NewsItem("VnExpress", "V1", "u1", datetime(2026, 9, 14, 9, 0, tzinfo=TZ)),
        NewsItem("Vietstock", "S2", "u2", datetime(2026, 9, 14, 10, 11, tzinfo=TZ)),
        NewsItem("Vietstock", "S1", "u3", datetime(2026, 9, 14, 10, 3, tzinfo=TZ)),
    ]
    grouped = scheduler._group_pending_by_source(pending)

    assert list(grouped.keys()) == ["Vietstock", "VnExpress"]  # Tuổi Trẻ dropped: nothing pending
    assert [i.title for i in grouped["Vietstock"]] == ["S1", "S2"]  # oldest-first within a source

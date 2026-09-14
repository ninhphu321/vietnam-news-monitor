from datetime import datetime
from zoneinfo import ZoneInfo

from models import NewsItem

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def make_item(url="https://vnexpress.net/a-123.html", title="Tiêu đề A"):
    return NewsItem(
        source="VnExpress",
        title=title,
        url=url,
        published_at=datetime(2026, 9, 14, 10, 0, tzinfo=TZ),
    )


def test_insert_if_new_returns_true_first_time(db):
    assert db.insert_if_new(make_item()) is True


def test_insert_if_new_returns_false_on_duplicate_url(db):
    item = make_item()
    assert db.insert_if_new(item) is True
    assert db.insert_if_new(item) is False
    assert db.count_all() == 1


def test_dedup_uses_url_not_title(db):
    # Spec section 5: must not dedup on title alone. Same title,
    # different URL -> both stored.
    a = make_item(url="https://vnexpress.net/a.html", title="Cùng tiêu đề")
    b = make_item(url="https://vnexpress.net/b.html", title="Cùng tiêu đề")
    assert db.insert_if_new(a) is True
    assert db.insert_if_new(b) is True
    assert db.count_all() == 2


def test_dedup_normalizes_tracking_params_before_checking(db):
    a = make_item(url="https://vnexpress.net/a-123.html")
    assert db.insert_if_new(a) is True

    b = make_item(url="https://vnexpress.net/a-123.html?utm_source=telegram&utm_medium=rss")
    assert db.url_exists(b.url) is True
    assert db.insert_if_new(b) is False
    assert db.count_all() == 1


def test_url_exists_false_for_unknown_url(db):
    assert db.url_exists("https://vnexpress.net/never-seen.html") is False


def test_get_pending_excludes_sent_and_initial_seen(db):
    a = make_item(url="https://vnexpress.net/pending.html")
    b = make_item(url="https://vnexpress.net/already-sent.html")
    c = make_item(url="https://vnexpress.net/baseline.html")

    db.insert_if_new(a)
    db.insert_if_new(b)
    db.insert_if_new(c, initial_seen=True)
    db.mark_sent([b.url])

    pending_urls = {i.url for i in db.get_pending()}
    assert pending_urls == {a.url}


def test_mark_sent_persists(db):
    a = make_item()
    db.insert_if_new(a)
    assert db.get_pending() != []
    db.mark_sent([a.url])
    assert db.get_pending() == []


def test_restart_does_not_lose_or_resend_state(tmp_path):
    """Spec acceptance: restart must not lose the DB and must not
    resend old articles."""
    from database import Database

    path = tmp_path / "news.db"
    db1 = Database(path)
    item = make_item()
    db1.insert_if_new(item)
    db1.mark_sent([item.url])

    # Simulate an app restart: a brand-new Database instance against
    # the same file.
    db2 = Database(path)
    assert db2.count_all() == 1
    assert db2.url_exists(item.url) is True
    assert db2.get_pending() == []  # already sent -> must not resend


def test_is_empty(db):
    assert db.is_empty() is True
    db.insert_if_new(make_item())
    assert db.is_empty() is False


def test_known_sources_reflects_distinct_sources(db):
    assert db.known_sources() == set()
    db.insert_if_new(NewsItem("A", "t", "https://x/1", datetime.now(TZ)))
    db.insert_if_new(NewsItem("B", "t", "https://x/2", datetime.now(TZ)))
    db.insert_if_new(NewsItem("A", "t2", "https://x/3", datetime.now(TZ)))
    assert db.known_sources() == {"A", "B"}


def test_last_new_article_at_none_when_source_unknown(db):
    assert db.last_new_article_at("Nobody") is None


def test_last_new_article_at_tracks_most_recent_insert(db):
    db.insert_if_new(NewsItem("A", "old", "https://x/1", datetime(2026, 9, 10, 9, 0, tzinfo=TZ)))
    before = db.last_new_article_at("A")
    assert before is not None

    db.insert_if_new(NewsItem("A", "new", "https://x/2", datetime(2026, 9, 14, 9, 0, tzinfo=TZ)))
    after = db.last_new_article_at("A")
    assert after >= before  # tracks first_seen_at (insert time), not published_at


def test_last_new_article_at_ignores_duplicate_inserts():
    """A stale feed that keeps re-offering the same URLs must NOT look
    fresh just because insert_if_new() was called again — rowcount 0
    means first_seen_at doesn't move."""
    from database import Database
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as d:
        db = Database(Path(d) / "news.db")
        item = NewsItem("A", "t", "https://x/1", datetime.now(TZ))
        db.insert_if_new(item)
        first = db.last_new_article_at("A")
        db.insert_if_new(item)  # duplicate URL, no-op
        assert db.last_new_article_at("A") == first


def test_stale_alert_roundtrip(db):
    assert db.get_stale_alert("VietnamNet") is None
    when = datetime(2026, 9, 14, 12, 0, tzinfo=TZ)
    db.set_stale_alert("VietnamNet", when)
    assert db.get_stale_alert("VietnamNet") == when

    later = datetime(2026, 9, 15, 8, 0, tzinfo=TZ)
    db.set_stale_alert("VietnamNet", later)  # upsert, not a duplicate row
    assert db.get_stale_alert("VietnamNet") == later

    db.clear_stale_alert("VietnamNet")
    assert db.get_stale_alert("VietnamNet") is None

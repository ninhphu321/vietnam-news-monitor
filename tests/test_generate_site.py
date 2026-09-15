from datetime import date, datetime
from zoneinfo import ZoneInfo

from models import NewsItem
from web.generate_site import build_site, group_by_date_and_source, render_day_page

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _article(source, title, url, published_at=None, first_seen_at=None):
    return {
        "source": source,
        "title": title,
        "url": url,
        "published_at": published_at,
        "first_seen_at": first_seen_at or published_at or datetime(2026, 9, 14, 8, 0, tzinfo=TZ),
    }


def test_group_by_date_and_source_uses_published_at_when_present():
    articles = [
        _article("VnExpress", "A", "u1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ)),
        _article("VnExpress", "B", "u2", datetime(2026, 9, 15, 9, 0, tzinfo=TZ)),
    ]
    grouped = group_by_date_and_source(articles)

    assert set(grouped.keys()) == {date(2026, 9, 14), date(2026, 9, 15)}
    assert [a["title"] for a in grouped[date(2026, 9, 14)]["VnExpress"]] == ["A"]


def test_group_by_date_falls_back_to_first_seen_at_when_published_at_missing():
    """Báo Đầu tư never has a published_at (documented limitation) — it
    must still land under a real date, not get dropped or crash."""
    articles = [_article("Báo Đầu tư", "No date", "u1", published_at=None,
                          first_seen_at=datetime(2026, 9, 14, 12, 0, tzinfo=TZ))]
    grouped = group_by_date_and_source(articles)

    assert list(grouped[date(2026, 9, 14)]["Báo Đầu tư"])[0]["title"] == "No date"


def test_group_by_date_and_source_sorts_newest_first_within_source():
    articles = [
        _article("VnExpress", "old", "u1", datetime(2026, 9, 14, 8, 0, tzinfo=TZ)),
        _article("VnExpress", "new", "u2", datetime(2026, 9, 14, 20, 0, tzinfo=TZ)),
    ]
    grouped = group_by_date_and_source(articles)
    titles = [a["title"] for a in grouped[date(2026, 9, 14)]["VnExpress"]]
    assert titles == ["new", "old"]


def test_render_day_page_includes_titles_links_and_date_nav():
    day = date(2026, 9, 14)
    sources = {"VnExpress": [_article("VnExpress", "Tiêu đề <script>", "https://x/1",
                                       datetime(2026, 9, 14, 10, 30, tzinfo=TZ))]}
    html = render_day_page(day, sources, [date(2026, 9, 15), date(2026, 9, 14)])

    assert "VnExpress" in html
    assert "https://x/1" in html
    assert "10:30" in html
    assert "14/09/2026" in html
    # Title is HTML-escaped, not injected raw (XSS guard for scraped titles).
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    # Both dates appear in the nav, including days with no content shown here.
    assert "15/09/2026" in html


def test_render_day_page_handles_empty_day():
    html = render_day_page(date(2026, 9, 14), {}, [date(2026, 9, 14)])
    assert "Không có bài nào" in html


def test_build_site_writes_one_file_per_date_plus_index(tmp_path, db):
    db.insert_if_new(NewsItem("VnExpress", "Day1", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ)))
    db.insert_if_new(NewsItem("VnExpress", "Day2", "https://x/2", datetime(2026, 9, 15, 10, 0, tzinfo=TZ)))

    out_dir = tmp_path / "site"
    build_site(db, out_dir=out_dir)

    assert (out_dir / "2026-09-14.html").exists()
    assert (out_dir / "2026-09-15.html").exists()
    assert (out_dir / "index.html").exists()
    assert (out_dir / ".nojekyll").exists()
    # index.html mirrors the latest date (15th), not the oldest.
    assert "Day2" in (out_dir / "index.html").read_text(encoding="utf-8")


def test_build_site_overwrites_stale_files_from_a_previous_run(tmp_path, db):
    """Regression guard: build_site must fully replace out_dir, not just
    add to it — an article deleted/renamed between runs (shouldn't
    normally happen, but the db is hand-editable) must not leave a
    stale HTML file behind forever."""
    out_dir = tmp_path / "site"
    out_dir.mkdir()
    (out_dir / "stale-leftover.html").write_text("old", encoding="utf-8")

    build_site(db, out_dir=out_dir)

    assert not (out_dir / "stale-leftover.html").exists()

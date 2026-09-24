from datetime import date, datetime
from zoneinfo import ZoneInfo

from config import config
from models import NewsItem
from web.generate_site import _tab_window, build_site, group_by_date_and_source, render_day_page
from web.issues import Issue

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
    assert "14/09/2026" in html  # in the masthead subtitle
    # Title is HTML-escaped, not injected raw (XSS guard for scraped
    # titles) — checked against the exact injected substring rather than
    # a bare "<script>" search, since the page legitimately has its own
    # <script> block for the news-stream filter/sort interactions.
    assert "Tiêu đề <script>" not in html
    assert "&lt;script&gt;" in html
    # Both dates appear as tabs (dd/mm, no year needed in a 7-day strip),
    # including days with no content shown here.
    assert '<a href="2026-09-14.html" class="active">14/09</a>' in html
    assert '<a href="2026-09-15.html">15/09</a>' in html
    # Only 2 dates total (well under the 7-tab window) -> no "Ngày khác" picker.
    assert "Ngày khác" not in html


def test_render_day_page_handles_empty_day():
    html = render_day_page(date(2026, 9, 14), {}, [date(2026, 9, 14)])
    assert "Không có bài nào" in html


def test_render_day_page_shows_date_picker_when_more_dates_than_the_tab_window():
    all_dates = [date(2026, 9, d) for d in range(15, 1, -1)]  # 14 dates, newest first
    html = render_day_page(date(2026, 9, 15), {}, all_dates)

    assert "Ngày khác" in html
    assert 'value="2026-09-02.html"' in html  # oldest date still reachable via the picker


def test_tab_window_returns_everything_when_fewer_dates_than_the_window():
    all_dates = [date(2026, 9, 15), date(2026, 9, 14)]
    assert _tab_window(all_dates, date(2026, 9, 14)) == all_dates


def test_tab_window_centers_on_the_current_day():
    all_dates = [date(2026, 9, d) for d in range(20, 0, -1)]  # 20 dates, newest first
    window = _tab_window(all_dates, date(2026, 9, 10), size=7)

    assert len(window) == 7
    assert date(2026, 9, 10) in window
    assert window.index(date(2026, 9, 10)) == 3  # 3 newer dates before it, centered


def test_tab_window_clamps_at_the_oldest_end():
    """Viewing the very oldest day must still fill a full 7-tab strip
    (from the oldest end) instead of a lopsided 1-tab sliver."""
    all_dates = [date(2026, 9, d) for d in range(20, 0, -1)]
    oldest = all_dates[-1]
    window = _tab_window(all_dates, oldest, size=7)

    assert len(window) == 7
    assert window[-1] == oldest


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


def test_build_site_points_archived_days_back_to_the_latest_day(tmp_path, db):
    """A bookmarked/shared link to an old dated page (e.g. "2026-09-14.html")
    stays frozen on that day forever by design (it's the archive) — the
    page must carry a banner pointing back to whichever day is actually
    latest, so a user landing there isn't stuck without knowing how to
    get to today's news. The latest day's own page (and index.html, its
    mirror) must NOT show that banner about itself."""
    db.insert_if_new(NewsItem("VnExpress", "Day1", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ)))
    db.insert_if_new(NewsItem("VnExpress", "Day2", "https://x/2", datetime(2026, 9, 15, 10, 0, tzinfo=TZ)))

    out_dir = tmp_path / "site"
    build_site(db, out_dir=out_dir)

    old_page = (out_dir / "2026-09-14.html").read_text(encoding="utf-8")
    latest_page = (out_dir / "2026-09-15.html").read_text(encoding="utf-8")
    index_page = (out_dir / "index.html").read_text(encoding="utf-8")

    assert 'class="latest-banner"' in old_page
    assert 'href="2026-09-15.html"' in old_page
    assert 'class="latest-banner"' not in latest_page
    assert 'class="latest-banner"' not in index_page


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


def test_scan_button_hidden_when_worker_url_not_configured(monkeypatch):
    """No Worker deployed -> nothing safe for the button to call, so it
    must not render (never a dead/broken button on a fresh checkout)."""
    monkeypatch.setattr(config, "scan_worker_url", "")
    html = render_day_page(date(2026, 9, 14), {}, [date(2026, 9, 14)])
    assert "Quét ngay" not in html


def test_scan_button_shown_and_calls_the_configured_worker_url(monkeypatch):
    monkeypatch.setattr(config, "scan_worker_url", "https://scan.example.workers.dev")
    html = render_day_page(date(2026, 9, 14), {}, [date(2026, 9, 14)])

    assert "Quét ngay" in html
    # The URL must reach the page as a JS string literal the button's
    # fetch() call actually uses, not just appear anywhere in the HTML.
    assert 'fetch("https://scan.example.workers.dev"' in html
    # The token that can actually trigger a crawl must never appear on
    # this (public) page — only the Worker's own environment has it.
    assert "GITHUB_TOKEN" not in html and "ghp_" not in html


def _issue(**overrides):
    defaults = dict(
        issue_id="eximbank-nhan-su",
        issue_title="Eximbank · Nhân sự lãnh đạo",
        entities=["eximbank"],
        topics=["nhân sự lãnh đạo"],
        article_count=5,
        unique_source_count=3,
        first_seen_at=datetime(2026, 9, 14, 9, 0, tzinfo=TZ),
        last_seen_at=datetime(2026, 9, 14, 16, 0, tzinfo=TZ),
        velocity=1.2,
        acceleration=1.5,
        volume_score=100.0,
        source_score=100.0,
        velocity_score=80.0,
        novelty_score=60.0,
        hot_score=88.5,
        sources=["VnExpress", "CafeF", "Tuổi Trẻ"],
        why_hot=["3 nguồn báo cùng đề cập", "xuất hiện 5 bài trong ngày"],
        representative_articles=[
            {"title": "Eximbank gia hạn đề cử nhân sự HĐQT", "url": "https://x/1", "source": "VnExpress"},
        ],
        all_articles=[
            {"title": "Eximbank gia hạn đề cử nhân sự HĐQT", "url": "https://x/1", "source": "VnExpress"},
        ],
    )
    defaults.update(overrides)
    return Issue(**defaults)


def test_top_issues_section_hidden_when_no_issues():
    html = render_day_page(date(2026, 9, 14), {}, [date(2026, 9, 14)], trending=[])
    assert "Top Issues" not in html


def test_top_issues_card_renders_rank_score_why_hot_metrics_coverage_and_related_articles():
    html = render_day_page(date(2026, 9, 14), {}, [date(2026, 9, 14)], trending=[_issue()])

    assert "Top Issues" in html
    assert 'issue-rank">01<' in html
    assert "Eximbank" in html
    assert "HOT 88" in html  # hot_score, rounded for display
    assert "5 bài" in html and "3 nguồn" in html
    # Why Hot is capped at 2 bullets on the compact card (design spec:
    # keep the collapsed card around 180-220px tall).
    assert "3 nguồn báo cùng đề cập" in html
    assert "xuất hiện 5 bài trong ngày" in html
    # Metrics (the 4 HotScore components) are exposed for debuggability.
    assert "Khối lượng" in html and "Tốc độ" in html
    # Source coverage bars + the full related-article list live in the
    # expanded detail body, which is present in the raw HTML regardless
    # of the <details> open/closed state.
    assert 'class="issue-detail"' in html
    assert 'class="source-coverage"' in html
    assert "https://x/1" in html
    assert ">VnExpress<" in html


def test_top_issues_omitted_on_non_latest_day_pages(tmp_path, db, monkeypatch):
    """Trending is computed relative to *today* (wall-clock "now") —
    showing it on an older archive day's page would misleadingly imply
    it reflects that day. build_site must only attach it to the latest
    day (see _top_issues_html's docstring)."""
    import web.generate_site as generate_site_module

    monkeypatch.setattr(generate_site_module, "top_issues", lambda articles, now: [_issue()])

    db.insert_if_new(NewsItem("VnExpress", "Old day article", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ)))
    db.insert_if_new(NewsItem("VnExpress", "Latest day article", "https://x/2", datetime(2026, 9, 15, 10, 0, tzinfo=TZ)))

    out_dir = tmp_path / "site"
    build_site(db, out_dir=out_dir)

    old_page = (out_dir / "2026-09-14.html").read_text(encoding="utf-8")
    latest_page = (out_dir / "2026-09-15.html").read_text(encoding="utf-8")
    assert "Top Issues" not in old_page
    assert "Top Issues" in latest_page


def test_news_stream_tags_articles_belonging_to_a_top_issue():
    """A row in the Unified News Stream whose URL matches one of the
    issue's articles gets an Issue Tag linking to that issue's card
    (spec: "Issue Tag → Issue Detail"); unrelated rows don't."""
    tagged = _article("VnExpress", "Eximbank gia hạn đề cử nhân sự HĐQT", "https://x/1",
                       datetime(2026, 9, 14, 9, 0, tzinfo=TZ))
    untagged = _article("CafeF", "Tin không liên quan", "https://x/9",
                         datetime(2026, 9, 14, 9, 0, tzinfo=TZ))
    sources = {"VnExpress": [tagged], "CafeF": [untagged]}

    html = render_day_page(date(2026, 9, 14), sources, [date(2026, 9, 14)], trending=[_issue()])

    assert 'data-issue="eximbank-nhan-su"' in html
    assert 'href="#issue-eximbank-nhan-su"' in html
    assert 'data-issue=""' in html  # the untagged row


def test_filters_list_present_sources_and_issues():
    sources = {"VnExpress": [_article("VnExpress", "A", "u1", datetime(2026, 9, 14, 9, 0, tzinfo=TZ))]}
    html = render_day_page(date(2026, 9, 14), sources, [date(2026, 9, 14)], trending=[_issue()])

    assert '<option value="VnExpress">VnExpress</option>' in html
    assert '<option value="eximbank-nhan-su">Eximbank · Nhân sự lãnh đạo</option>' in html


def test_by_source_section_still_lists_every_source_and_headline():
    sources = {"VnExpress": [_article("VnExpress", "Tiêu đề nguồn", "https://x/1",
                                       datetime(2026, 9, 14, 10, 30, tzinfo=TZ))]}
    html = render_day_page(date(2026, 9, 14), sources, [date(2026, 9, 14)])

    assert 'id="sources"' in html
    assert "Tiêu đề nguồn" in html


def test_news_stream_has_a_pagination_container_and_client_side_page_size():
    """All News shows 15 rows at a time (user request: too many articles
    at once) — every row is still in the DOM (search/filter need the
    full set), and JS slices + paginates client-side rather than the
    server pre-splitting into separate pages."""
    from web.generate_site import _NEWS_PAGE_SIZE

    html = render_day_page(date(2026, 9, 14), {}, [date(2026, 9, 14)])

    assert 'id="news-pagination" class="pagination"' in html
    assert f"var PAGE_SIZE = {_NEWS_PAGE_SIZE};" in html
    assert _NEWS_PAGE_SIZE == 15



def test_home_pages_link_to_the_analytics_tab_but_do_not_embed_it():
    """Analytics lives on its own page (analytics.html): the home page
    only carries a nav link, never the analytics section itself."""
    html = render_day_page(date(2026, 9, 14), {}, [date(2026, 9, 14)], has_analytics=True)
    assert 'href="analytics.html"' in html
    assert 'id="analytics"' not in html
    assert "Ai đưa tin trước" not in html

    no_data = render_day_page(date(2026, 9, 14), {}, [date(2026, 9, 14)])
    assert 'href="analytics.html"' not in no_data


def test_build_site_writes_analytics_tab_and_data_exports(tmp_path, db):
    import json

    db.insert_if_new(NewsItem("VnExpress", "Old day", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ)))
    db.insert_if_new(NewsItem("CafeF", "Latest & day", "https://x/2", datetime(2026, 9, 15, 10, 0, tzinfo=TZ)))
    out_dir = tmp_path / "site"
    build_site(db, out_dir=out_dir)

    analytics = (out_dir / "analytics.html").read_text(encoding="utf-8")
    assert 'id="analytics"' in analytics and "Ai đưa tin trước" in analytics
    assert 'href="index.html"' in analytics

    for page in ("index.html", "2026-09-14.html", "2026-09-15.html"):
        text = (out_dir / page).read_text(encoding="utf-8")
        assert 'href="analytics.html"' in text and 'id="analytics"' not in text

    assert "issues" in json.loads((out_dir / "issues.json").read_text(encoding="utf-8"))
    assert "daily" in json.loads((out_dir / "stats.json").read_text(encoding="utf-8"))
    feed = (out_dir / "feed.xml").read_text(encoding="utf-8")
    assert "<rss" in feed and "Latest &amp; day" in feed


def test_build_site_writes_brands_tab_with_share_of_voice_and_export(tmp_path, db):
    import json

    for i, src in enumerate(["CafeF", "VnExpress", "Dân Trí"]):
        db.insert_if_new(NewsItem(src, f"Techcombank vinh danh lần {i}", f"https://x/t{i}",
                                  datetime(2026, 9, 15, 10, i, tzinfo=TZ)))
    out_dir = tmp_path / "site"
    build_site(db, out_dir=out_dir)

    brands = (out_dir / "brands.html").read_text(encoding="utf-8")
    assert "Share of voice" in brands and "Techcombank" in brands and "Cảnh báo khủng hoảng" in brands
    assert 'href="analytics.html"' in brands and 'class="active"' in brands
    data = json.loads((out_dir / "brands.json").read_text(encoding="utf-8"))
    assert {"share_of_voice_7d", "share_of_voice_30d", "crisis_alerts", "watchlist"} <= set(data)

    home = (out_dir / "index.html").read_text(encoding="utf-8")
    assert 'href="brands.html"' in home and 'id="filter-brand"' in home
    assert 'data-brand="|Techcombank|"' in home
    assert 'class="sent pos"' in home   # "vinh danh" -> positive dot


def test_news_rows_show_a_negative_dot_with_the_triggering_keywords(tmp_path, db):
    db.insert_if_new(NewsItem("CafeF", "Sacombank bị phạt vì vi phạm", "https://x/1",
                              datetime(2026, 9, 15, 10, 0, tzinfo=TZ)))
    out_dir = tmp_path / "site"
    build_site(db, out_dir=out_dir)
    home = (out_dir / "index.html").read_text(encoding="utf-8")
    assert 'class="sent neg"' in home and "bị phạt" in home

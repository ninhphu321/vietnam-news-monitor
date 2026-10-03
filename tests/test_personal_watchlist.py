"""Tests for personal_watchlist.py (roadmap V4 §29-34) — the private,
local-only, Telegram-only watchlist. See its module docstring for why
this is a separate file from web/brands.py's watchlist.json."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from models import NewsItem
from personal_watchlist import load_personal_watchlist, match_new_articles

TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def test_missing_file_disables_the_feature(tmp_path):
    assert load_personal_watchlist(tmp_path / "does-not-exist.json") is None


def test_none_path_disables_the_feature():
    assert load_personal_watchlist(None) is None


def test_unreadable_json_disables_the_feature(tmp_path):
    path = tmp_path / "personal_watchlist.json"
    path.write_text("not valid json {{{", encoding="utf-8")
    assert load_personal_watchlist(path) is None


def test_empty_entities_list_disables_the_feature(tmp_path):
    path = tmp_path / "personal_watchlist.json"
    path.write_text(json.dumps({"entities": []}), encoding="utf-8")
    assert load_personal_watchlist(path) is None


def test_loads_entities_and_matches_titles(tmp_path):
    path = tmp_path / "personal_watchlist.json"
    path.write_text(json.dumps({"entities": ["Vietcombank", "FPT"]}), encoding="utf-8")
    index = load_personal_watchlist(path)
    assert index is not None
    assert index.detect("Vietcombank tăng lãi suất huy động") == ["Vietcombank"]
    assert index.detect("Tin không liên quan") == []


def test_extra_aliases_are_merged_in(tmp_path):
    path = tmp_path / "personal_watchlist.json"
    path.write_text(json.dumps({
        "entities": ["Ngân hàng Nhà nước"],
        "extra_aliases": {"Ngân hàng Nhà nước": ["NHNN"]},
    }), encoding="utf-8")
    index = load_personal_watchlist(path)
    assert index.detect("NHNN vừa công bố quyết định mới") == ["Ngân hàng Nhà nước"]


def test_short_ticker_alias_matches_case_sensitively(tmp_path):
    # Same BrandIndex semantics as web/brands.py: a short ALL-CAPS alias
    # ("FPT") must not match lowercase "fpt" inside unrelated text.
    path = tmp_path / "personal_watchlist.json"
    path.write_text(json.dumps({"entities": ["FPT"]}), encoding="utf-8")
    index = load_personal_watchlist(path)
    assert index.detect("FPT công bố lợi nhuận quý 3") == ["FPT"]
    assert index.detect("fpt là viết tắt của...") == []


def _item(source, title):
    return NewsItem(source, title, f"https://x/{source}/{title}", datetime(2026, 9, 14, 10, 0, tzinfo=TZ))


def test_match_new_articles_counts_articles_and_distinct_sources(tmp_path):
    path = tmp_path / "personal_watchlist.json"
    path.write_text(json.dumps({"entities": ["Vietcombank", "FPT"]}), encoding="utf-8")
    index = load_personal_watchlist(path)

    articles = [
        _item("VnExpress", "Vietcombank tăng lãi suất"),
        _item("CafeF", "Vietcombank mở chi nhánh mới"),
        _item("VnExpress", "Tin không liên quan"),
    ]
    matches = match_new_articles(index, articles)
    assert len(matches) == 1
    assert matches[0].entity == "Vietcombank"
    assert matches[0].new_article_count == 2
    assert matches[0].new_source_count == 2


def test_match_new_articles_empty_when_nothing_matches(tmp_path):
    path = tmp_path / "personal_watchlist.json"
    path.write_text(json.dumps({"entities": ["Vietcombank"]}), encoding="utf-8")
    index = load_personal_watchlist(path)
    assert match_new_articles(index, [_item("VnExpress", "Tin không liên quan")]) == []


# --- Secret path for GitHub Actions (PERSONAL_WATCHLIST_JSON) ----------------------
def test_raw_json_is_used_when_there_is_no_file(tmp_path):
    index = load_personal_watchlist(tmp_path / "missing.json", '{"entities": ["Vietcombank"]}')
    assert index is not None and index.detect("Vietcombank tăng lãi suất") == ["Vietcombank"]


def test_raw_json_takes_precedence_over_the_file(tmp_path):
    path = tmp_path / "personal_watchlist.json"
    path.write_text(json.dumps({"entities": ["FPT"]}), encoding="utf-8")
    index = load_personal_watchlist(path, '{"entities": ["ACB"]}')
    assert index.detect("ACB báo lãi") == ["ACB"]
    assert index.detect("FPT báo lãi") == []


def test_invalid_raw_json_disables_the_feature_instead_of_falling_back_to_the_file(tmp_path):
    path = tmp_path / "personal_watchlist.json"
    path.write_text(json.dumps({"entities": ["FPT"]}), encoding="utf-8")
    assert load_personal_watchlist(path, "{not json") is None


def test_blank_raw_json_falls_back_to_the_file(tmp_path):
    # An unset GitHub Secret reaches the job as an empty string, not as "missing".
    path = tmp_path / "personal_watchlist.json"
    path.write_text(json.dumps({"entities": ["FPT"]}), encoding="utf-8")
    assert load_personal_watchlist(path, "   ").detect("FPT báo lãi") == ["FPT"]
    assert load_personal_watchlist(tmp_path / "missing.json", "") is None


def test_raw_json_that_is_not_an_object_disables_the_feature():
    assert load_personal_watchlist(None, '["Vietcombank"]') is None


def test_config_reads_the_secret_from_the_environment(monkeypatch):
    from config import Config
    monkeypatch.setenv("PERSONAL_WATCHLIST_JSON", '{"entities": ["ACB"]}')
    assert Config().personal_watchlist_json == '{"entities": ["ACB"]}'
    monkeypatch.delenv("PERSONAL_WATCHLIST_JSON")
    assert Config().personal_watchlist_json == ""


def test_run_cycle_alert_works_from_the_secret_and_never_logs_the_watched_names(db, monkeypatch, caplog):
    # On GitHub Actions in a public repo the job log is world-readable, so
    # the private entity names must not appear in it.
    import scheduler
    import telegram
    from config import Config

    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: sent.append(a[2]))
    cfg = Config(telegram_bot_token="t", telegram_chat_id="c", request_timeout=1, max_retries=1,
                 personal_watchlist_path=None, personal_watchlist_json='{"entities": ["Vietcombank"]}')
    items = [NewsItem("A", "Vietcombank tăng lãi suất", "https://x/1", datetime(2026, 9, 14, 10, 0, tzinfo=TZ))]

    with caplog.at_level("DEBUG"):
        scheduler.send_personal_watchlist_alert(cfg, datetime(2026, 9, 14, 12, 0, tzinfo=TZ), items)

    assert any("Vietcombank" in text for text in sent)       # the Telegram message carries it...
    assert "Vietcombank" not in caplog.text                  # ...the log does not
    assert "1 watched item" in caplog.text

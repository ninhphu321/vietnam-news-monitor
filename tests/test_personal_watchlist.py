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

"""Tests for brand monitoring: dictionary, watchlist, tone, share of
voice, crisis alerts and the scheduler's alert cooldown."""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import telegram
from config import Config
from models import NewsItem
from scheduler import check_crisis
from web.brands import DEFAULT_BRANDS, BrandIndex, load_watchlist
from web.brandwatch import crisis_alerts, share_of_voice, tag_articles
from web.sentiment import NEGATIVE, NEUTRAL, POSITIVE, classify

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
NOW = datetime(2026, 9, 17, 12, 0, tzinfo=TZ)
INDEX = BrandIndex(DEFAULT_BRANDS)


def _art(source, title, minutes_ago=5):
    when = NOW - timedelta(minutes=minutes_ago)
    return {"source": source, "title": title, "url": f"https://x/{source}/{title}",
            "published_at": when, "first_seen_at": when}


# --- brand dictionary ---------------------------------------------------------
def test_aliases_and_tickers_map_to_the_canonical_brand():
    assert INDEX.detect("VCB công bố lợi nhuận") == ["Vietcombank"]
    assert INDEX.detect("Ngân hàng Ngoại thương tăng vốn") == ["Vietcombank"]
    assert INDEX.detect("Techcombank và VPBank cạnh tranh") == ["Techcombank", "VPBank"]


def test_short_tickers_are_case_sensitive_so_common_words_do_not_match():
    assert INDEX.detect("MB đóng góp ngân sách") == ["MB"]
    assert INDEX.detect("Tải file 20 mb về máy") == []
    assert INDEX.detect("Dung lượng 5MB") == []          # no word boundary before "MB"
    assert INDEX.detect("MBBank ra mắt ứng dụng") == ["MB"]


def test_alias_matches_whole_words_only():
    assert INDEX.detect("ABBank tăng vốn") == ["ABBank"]   # not also "ABB"-something else
    assert INDEX.detect("Chuyện SHBank không tồn tại") == []


def test_watchlist_file_adds_aliases_custom_brands_and_own_competitors(tmp_path):
    path = tmp_path / "watchlist.json"
    path.write_text(json.dumps({
        "own": ["Techcombank"], "competitors": ["VPBank", "Vingroup"],
        "extra_aliases": {"Techcombank": ["Techcom"]},
        "extra_negative_keywords": ["thanh tra"],
    }), encoding="utf-8")
    index, watch = load_watchlist(path)
    assert watch.own == ["Techcombank"] and watch.tracked == ["Techcombank", "VPBank", "Vingroup"]
    assert index.detect("Techcom mở chi nhánh") == ["Techcombank"]
    assert index.detect("Vingroup khởi công") == ["Vingroup"]   # unknown name -> custom brand
    assert watch.negative_extra == ["thanh tra"]


def test_missing_or_broken_watchlist_falls_back_to_defaults(tmp_path):
    index, watch = load_watchlist(tmp_path / "nope.json")
    assert watch.tracked == [] and "Vietcombank" in index.brands
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    assert load_watchlist(bad)[1].tracked == []


# --- sentiment ----------------------------------------------------------------
def test_tone_labels_and_reasons():
    neg = classify("Ngân hàng X bị khởi tố vụ án")
    assert neg.label == NEGATIVE and neg.severity == 3 and neg.reasons == ["khởi tố"] and neg.is_crisis_grade
    pos = classify("MB vinh danh lợi nhuận kỷ lục")
    assert pos.label == POSITIVE and not pos.is_crisis_grade
    assert classify("Lãi suất huy động hôm nay").label == NEUTRAL


def test_mild_negatives_colour_tone_but_never_crisis_grade():
    s = classify("Không phải mọi tỷ lệ nợ xấu đều như nhau")
    assert s.label == NEGATIVE and s.severity == 1 and not s.is_crisis_grade


def test_denial_of_a_rumour_is_neutral_not_bad_news():
    s = classify("Techcombank bác bỏ tin đồn rút tiền ồ ạt")
    assert s.label == NEUTRAL and s.denial and not s.is_crisis_grade


def test_protective_framing_does_not_turn_scam_words_negative():
    s = classify("SHB mở rộng tính năng cảnh báo tài khoản có dấu hiệu lừa đảo")
    assert s.label != NEGATIVE
    # ...but a truly critical event still counts even with protective words around
    assert classify("Giám đốc bị khởi tố, ngân hàng tăng cường bảo mật").label == NEGATIVE


def test_debt_recovery_is_not_a_licence_recall():
    assert classify("SCB đã thu hồi gần 900 tỷ liên quan bản án").label != NEGATIVE
    assert classify("Ngân hàng X bị thu hồi giấy phép").label == NEGATIVE


def test_longest_keyword_wins_over_its_substring():
    assert classify("Nợ xấu tăng vọt tại ngân hàng Y").severity == 2   # "nợ xấu tăng vọt" (strong), not mild "nợ xấu"


def test_watchlist_negative_keywords_are_strong():
    assert classify("Ngân hàng Z bị thẩm định lại").label == NEUTRAL
    assert classify("Ngân hàng Z bị thẩm định lại", ["thẩm định lại"]).is_crisis_grade


# --- share of voice -----------------------------------------------------------
def test_share_of_voice_counts_shares_tone_and_previous_period():
    arts = [_art("CafeF", "Techcombank vinh danh", 60), _art("VnExpress", "Techcombank lãi kỷ lục", 120),
            _art("Dân Trí", "VPBank bị phạt vi phạm", 180)]
    arts.append({**_art("CafeF", "Techcombank kỳ trước", 0), "published_at": NOW - timedelta(days=9),
                 "first_seen_at": NOW - timedelta(days=9)})
    _, watch = load_watchlist(None)
    tagged = tag_articles(arts, INDEX, watch)
    stats = {s.brand: s for s in share_of_voice(tagged, INDEX, watch, NOW, 7)}
    assert stats["Techcombank"].mentions == 2 and stats["Techcombank"].positive == 2
    assert stats["Techcombank"].previous_mentions == 1
    assert stats["VPBank"].negative == 1 and stats["VPBank"].mentions == 1
    assert stats["Techcombank"].share == pytest.approx(2 / 3)


def test_share_of_voice_is_limited_to_the_watchlist_when_configured(tmp_path):
    path = tmp_path / "w.json"
    path.write_text(json.dumps({"own": ["Techcombank"], "competitors": ["VPBank"]}), encoding="utf-8")
    index, watch = load_watchlist(path)
    tagged = tag_articles([_art("A", "Techcombank ra mắt"), _art("B", "BIDV ra mắt")], index, watch)
    stats = {s.brand: s for s in share_of_voice(tagged, index, watch, NOW, 7)}
    assert set(stats) == {"Techcombank", "VPBank"} and stats["Techcombank"].role == "own"
    assert stats["Techcombank"].share == 1.0     # BIDV is not tracked, so it doesn't dilute the share


# --- crisis alerts ------------------------------------------------------------
def _negative_wave(n_sources, keyword="bị phạt", minutes_ago=10):
    return [_art(f"Báo{i}", f"Sacombank {keyword} nặng", minutes_ago + i) for i in range(n_sources)]


def test_alert_needs_three_outlets_within_the_window():
    _, watch = load_watchlist(None)
    two = crisis_alerts(tag_articles(_negative_wave(2), INDEX, watch), NOW, watch, INDEX)
    three = crisis_alerts(tag_articles(_negative_wave(3), INDEX, watch), NOW, watch, INDEX)
    assert two == []
    assert len(three) == 1 and three[0].brand == "Sacombank" and three[0].level == "leo thang"
    assert len(three[0].sources) == 3 and "bị phạt" in three[0].keywords


def test_two_outlets_with_a_critical_keyword_is_urgent():
    _, watch = load_watchlist(None)
    alerts = crisis_alerts(tag_articles(_negative_wave(2, "bị khởi tố"), INDEX, watch), NOW, watch, INDEX)
    assert len(alerts) == 1 and alerts[0].level == "khẩn"


def test_old_or_mild_headlines_never_alert():
    _, watch = load_watchlist(None)
    stale = _negative_wave(4, minutes_ago=200)                      # outside the 60-minute window
    mild = [_art(f"Báo{i}", "Sacombank có nợ xấu", 5) for i in range(4)]   # mild only
    assert crisis_alerts(tag_articles(stale + mild, INDEX, watch), NOW, watch, INDEX) == []


def test_same_outlet_repeating_itself_counts_once():
    _, watch = load_watchlist(None)
    arts = [_art("CafeF", f"Sacombank bị phạt lần {i}", 5 + i) for i in range(5)]
    assert crisis_alerts(tag_articles(arts, INDEX, watch), NOW, watch, INDEX) == []


# --- scheduler: cooldown + urgent override ------------------------------------
def _cfg(tmp_path):
    return Config(telegram_bot_token="t", telegram_chat_id="c", watchlist_path=tmp_path / "none.json")


def _seed(db, n, keyword):
    for i in range(n):
        when = datetime.now(TZ) - timedelta(minutes=5 + i)
        db.insert_if_new(NewsItem(f"Báo{i}", f"Sacombank {keyword} nặng", f"https://x/{keyword}/{i}", when))


def test_check_crisis_sends_once_then_respects_cooldown(db, tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: sent.append(a[2]))
    _seed(db, 3, "bị phạt")
    now = datetime.now(TZ)
    check_crisis(db, _cfg(tmp_path), now)
    check_crisis(db, _cfg(tmp_path), now + timedelta(minutes=20))
    assert len(sent) == 1 and "Sacombank" in sent[0] and "LEO THANG" in sent[0]
    check_crisis(db, _cfg(tmp_path), now + timedelta(hours=4))   # the wave is 4h old by now: nothing new to page about
    assert len(sent) == 1


def test_urgent_alert_overrides_the_cooldown_of_an_earlier_escalation(db, tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(telegram, "send_message", lambda *a, **k: sent.append(a[2]))
    _seed(db, 3, "bị phạt")
    now = datetime.now(TZ)
    check_crisis(db, _cfg(tmp_path), now)
    _seed(db, 3, "bị khởi tố")
    check_crisis(db, _cfg(tmp_path), now + timedelta(minutes=5))
    assert len(sent) == 2 and "KHẨN" in sent[1]


def test_failed_telegram_send_is_retried_next_cycle_not_recorded(db, tmp_path, monkeypatch):
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise telegram.TelegramError("down")

    monkeypatch.setattr(telegram, "send_message", flaky)
    _seed(db, 3, "bị phạt")
    now = datetime.now(TZ)
    check_crisis(db, _cfg(tmp_path), now)
    assert db.get_crisis_alert("Sacombank") is None
    check_crisis(db, _cfg(tmp_path), now + timedelta(minutes=1))
    assert db.get_crisis_alert("Sacombank") is not None and calls["n"] == 2


def test_check_crisis_never_raises(db, tmp_path, monkeypatch):
    monkeypatch.setattr(db, "get_all_articles", lambda: 1 / 0)
    check_crisis(db, _cfg(tmp_path), datetime.now(TZ))

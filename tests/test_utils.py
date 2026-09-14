from utils import normalize_title, normalize_url


def test_normalize_title_trims_and_collapses_whitespace():
    assert (
        normalize_title("  Ngân hàng   tăng trưởng tín dụng mạnh  ")
        == "Ngân hàng tăng trưởng tín dụng mạnh"
    )


def test_normalize_title_never_rewrites_content():
    # Regression guard for spec 25: normalization must only touch
    # whitespace, never words.
    original = "Ngân hàng đang tăng trưởng cực mạnh"
    assert normalize_title(original) == original


def test_normalize_title_handles_none():
    assert normalize_title(None) == ""


def test_normalize_title_unescapes_html_entities():
    # Regression guard: Thanh Nien's RSS double-encodes accented
    # characters inside the CDATA <title> (e.g. "&agrave;" instead of
    # "à"), which feedparser leaves as literal text since CDATA is
    # plain text, not HTML.
    assert (
        normalize_title("Tuần n&agrave;y cổ phiếu n&agrave;o được mua v&agrave;o?")
        == "Tuần này cổ phiếu nào được mua vào?"
    )


def test_normalize_url_resolves_relative_to_absolute():
    assert (
        normalize_url("/article-123", base_url="https://domain.com/kinh-doanh")
        == "https://domain.com/article-123"
    )


def test_normalize_url_strips_utm_params():
    assert (
        normalize_url("https://vnexpress.net/abc-123.html?utm_source=rss&utm_medium=rss")
        == "https://vnexpress.net/abc-123.html"
    )


def test_normalize_url_strips_fbclid_but_keeps_unknown_params():
    result = normalize_url("https://example.com/a?fbclid=xyz&id=42")
    assert "fbclid" not in result
    assert "id=42" in result


def test_normalize_url_drops_fragment():
    assert normalize_url("https://example.com/a?x=1#section2") == "https://example.com/a?x=1"


def test_normalize_url_already_absolute_untouched_otherwise():
    url = "https://example.com/a-b-c-123.html"
    assert normalize_url(url) == url

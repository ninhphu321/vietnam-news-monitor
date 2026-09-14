"""Small stateless helpers shared by crawlers, database, and telegram.

Kept separate from crawlers/base.py so tests can exercise normalization
logic without importing feedparser/requests.
"""

import html
import re
from urllib.parse import urljoin, urlsplit, urlunsplit, parse_qsl, urlencode

# Query-string parameters that identify tracking/campaign noise, not the
# article itself. Kept short and easy to extend; anything not listed here
# is preserved so we never risk pointing at the wrong article (spec 5.26:
# "không làm thay đổi URL thực tế đến mức dẫn sai bài báo").
TRACKING_PARAM_PREFIXES = ("utm_",)
TRACKING_PARAM_EXACT = {
    "fbclid",
    "gclid",
    "gclsrc",
    "zarsrc",
    "ref",
    "spid",
}


def normalize_title(raw_title: str) -> str:
    """Trim and collapse internal whitespace. Never rewrites content.

    Also unescapes HTML entities (e.g. "&agrave;" -> "à"): some feeds
    (observed on Thanh Nien) double-encode accented characters inside
    the CDATA-wrapped <title>, which RSS parsers correctly leave as
    literal text since CDATA content is plain text, not HTML. This is
    a no-op for titles that contain no entities.
    """
    if raw_title is None:
        return ""
    unescaped = html.unescape(raw_title)
    # Collapse any run of whitespace (spaces, tabs, newlines) to a single
    # space, then strip the ends. Vietnamese diacritics are untouched
    # because we only match on \s.
    return re.sub(r"\s+", " ", unescaped).strip()


def normalize_url(raw_url: str, base_url: str = "") -> str:
    """Make a URL absolute and strip known tracking query params.

    Relative URLs (e.g. "/article-123") are resolved against base_url.
    Fragment identifiers are dropped (they never affect which article
    loads). Unknown query params are preserved untouched.
    """
    if raw_url is None:
        return ""
    raw_url = raw_url.strip()
    absolute = urljoin(base_url, raw_url) if base_url else raw_url

    parts = urlsplit(absolute)
    kept_params = [
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith(TRACKING_PARAM_PREFIXES)
        and k.lower() not in TRACKING_PARAM_EXACT
    ]
    new_query = urlencode(kept_params)
    normalized = urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, ""))
    return normalized

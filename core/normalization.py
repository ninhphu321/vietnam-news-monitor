"""News-title normalization (roadmap V1 §6: RAW NEWS -> NEWS NORMALIZATION).

Two separate concerns, kept in two separate functions:

  normalize_display_title() -- safe to store as the title a person reads.
      Whitespace/entity cleanup only. Never rewrites wording.

  normalize_for_matching() -- NEVER stored or shown; used only as the
      input to keyword/regex matching (web/issues.py entity+topic
      extraction, web/analytics.py repost detection, web/sentiment.py,
      web/brands.py). Adds Unicode canonicalization (NFC) and casefolding
      on top of the display normalization.

Why NFC matters here specifically: Vietnamese diacritics can be stored
as one precomposed codepoint ("ộ" = "ộ") or as a base letter plus
combining marks ("ô" + "̣" = "ô" + combining-dot-below, which
*renders* identically but is a different string). Confirmed on real
production data (2026-09-30 audit of data/news.db): a VietnamPlus RSS
title stored "xung đột" with a decomposed "ộ" (precomposed "ô" plus a
separate combining dấu nặng), which a regex looking for the precomposed
literal "đột" fails to match. NFC normalization makes both forms
compare equal without changing what a reader sees.

This does not introduce a second stored `normalized_title` column: the
project's `title` field already isn't the untouched raw feed value
(crawlers already run it through whitespace/entity cleanup before
storing — see utils.normalize_title), and Vietnamese NFC composition is
canonicalization, not a content change, so folding it into that same
single choke point fixes matching everywhere without every consumer
needing its own call to this module or a second column to keep in sync.
"""

import html
import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+")


def normalize_display_title(raw_title: str) -> str:
    """Trim, collapse whitespace, unescape HTML entities, and canonicalize
    Unicode composition. Safe to store/show: never changes wording."""
    if raw_title is None:
        return ""
    unescaped = html.unescape(raw_title)
    composed = unicodedata.normalize("NFC", unescaped)
    return _WHITESPACE_RE.sub(" ", composed).strip()


def normalize_for_matching(text: str) -> str:
    """Lowercased, NFC-composed text for keyword/entity matching only —
    never persisted, never displayed. Callers that already store a
    normalize_display_title() value only need `.lower()` plus this
    module's NFC guarantee; kept as a separate function so matching code
    reads as intent ("this text is about to be pattern-matched") rather
    than an unexplained `.lower()`."""
    if text is None:
        return ""
    return unicodedata.normalize("NFC", text).lower()

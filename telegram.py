"""Telegram Bot API integration: message formatting + sending.

Uses plain `requests` against the HTTP Bot API instead of the
`python-telegram-bot` package. That library is async-first (v20+) and
pulls in a fair amount of machinery for a need that is exactly one
synchronous POST per cycle — plain requests keeps this file small and
easy to read end-to-end, in line with spec section 33's "SIMPLE
STABLE MAINTAINABLE" priority.

Important invariant this module does NOT enforce (the caller does):
sent_at in the database must only be updated after send_message /
send_messages returns successfully. See scheduler.run_cycle().
"""

import html
import logging
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import requests

from models import NewsItem

logger = logging.getLogger(__name__)


class TelegramError(Exception):
    """Raised when a message could not be delivered after retries."""


# ---------------------------------------------------------------------------
# Formatting (pure functions, no network — easy to unit test)
#
# V2 groups new articles by source instead of one flat list (spec section
# 11): each source is a heading, its articles are bullet lines below it,
# title is a clickable HTML link (so the raw URL doesn't need to be shown),
# and messages are sent with parse_mode=HTML throughout. V3 polish: each
# source gets its own icon so the eye can tell sources apart at a glance
# without reading the (bold) name, and the message opens with a one-line
# summary (how many articles, from how many sources).
# ---------------------------------------------------------------------------

# Curated so recognizable sources get a fitting icon (VOV = radio, VTV =
# television, Chính phủ = a government building, VietnamPlus = a "+"...)
# rather than arbitrary colors. A source not listed here (a new crawler
# added later, before this dict is updated) falls back to a small pool
# picked by a stable hash of its name — never crashes, never blank.
SOURCE_ICONS: Dict[str, str] = {
    "VnExpress": "🔵",
    "Tuổi Trẻ": "🟠",
    "CafeF": "🏦",
    "Vietstock": "📊",
    "Thanh Niên": "🔴",
    "Dân Trí": "🟡",
    "VnEconomy": "📈",
    "Znews": "⚡",
    "Tiền Phong": "🟣",
    "VOV": "📻",
    "VietnamPlus": "➕",
    "Nhân Dân": "⭐",
    "Chính phủ": "🏛️",
    "VTV": "📺",
}
_FALLBACK_ICONS = ["🟢", "🔶", "🔷", "🟩", "🟦", "🟧"]

# Reserve room for the "(phần N/M)" part header added to each message only
# when a cycle is large enough to need splitting (see format_grouped_articles)
# — comfortably covers up to 3-digit part counts.
_PART_HEADER_RESERVE = 48


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _icon_for(source: str) -> str:
    if source in SOURCE_ICONS:
        return SOURCE_ICONS[source]
    # sum-of-codepoints instead of hash(): Python randomizes str hash()
    # per process by default, which would make an unmapped source's
    # fallback icon change across restarts.
    return _FALLBACK_ICONS[sum(map(ord, source)) % len(_FALLBACK_ICONS)]


def _time_str(item: NewsItem) -> Optional[str]:
    if item.published_at is None:
        return None
    return item.published_at.strftime("%H:%M")


def _article_line(item: NewsItem) -> str:
    link = f'<a href="{_esc(item.url)}">{_esc(item.title)}</a>'
    t = _time_str(item)
    return f"• {link} — {t}" if t else f"• {link}"


def _source_header(source: str, count: int) -> str:
    return f"{_icon_for(source)} <b>{_esc(source.upper())}</b> ({count} bài)"


def _source_block(source: str, items: List[NewsItem]) -> List[str]:
    lines = [_source_header(source, len(items)), ""]
    lines += [_article_line(i) for i in items]
    return lines


def format_grouped_articles(
    items_by_source: Dict[str, List[NewsItem]],
    limit: int = 4096,
    errored_sources: Optional[List[str]] = None,
) -> List[str]:
    """Build one (or more, only if over the char limit) Telegram message(s)
    grouping new articles by source.

    `items_by_source` must already be in the desired display order
    (spec section 12: config order, not sorted by time) and contain
    only sources that actually have pending articles. Within a source,
    caller is expected to have sorted articles oldest-first.

    Spec section 15: prefer exactly one message per cycle; only split
    into multiple parts when the combined text would exceed `limit`,
    and never cut a single article's line in half. `errored_sources`,
    if given, is appended as a trailing warning so a cycle with both
    new articles and a failing source never looks fully healthy
    (spec section 14).
    """
    sources = [s for s, items in items_by_source.items() if items]
    if not sources:
        return []

    total = sum(len(items_by_source[s]) for s in sources)
    summary = f"📬 <b>{total} bài mới</b> · {len(sources)} nguồn"

    footer = ""
    if errored_sources:
        footer = "\n\n⚠️ Nguồn lỗi: " + ", ".join(errored_sources)

    blocks = {s: _source_block(s, items_by_source[s]) for s in sources}
    body = "\n\n".join("\n".join(blocks[s]) for s in sources)
    full_text = f"{summary}\n\n{body}{footer}"
    if len(full_text) <= limit:
        return [full_text]

    # Pack whole source-blocks per message, reserving room for the
    # "(phần N/M)" header added to every message below; a single source
    # with so many articles that its own block exceeds that reduced
    # limit gets its bullet lines split across messages instead,
    # repeating its header.
    split_limit = limit - _PART_HEADER_RESERVE
    messages: List[str] = []
    current: List[str] = []

    def flush() -> None:
        if current:
            messages.append("\n".join(current))
            current.clear()

    for source in sources:
        items = items_by_source[source]
        header = _source_header(source, len(items))
        bullets = [_article_line(i) for i in items]
        block_text = header + "\n\n" + "\n".join(bullets)

        if len(block_text) <= split_limit:
            if len(block_text) + (len("\n".join(current)) + 2 if current else 0) > split_limit:
                flush()
            if current:
                current.append("")
            current.extend([header, ""])
            current.extend(bullets)
            continue

        # This one source alone has too many articles for one message.
        flush()
        chunk: List[str] = []
        chunk_len = len(header) + 2
        for bullet in bullets:
            if chunk and chunk_len + len(bullet) + 1 > split_limit:
                messages.append(header + "\n\n" + "\n".join(chunk))
                chunk = []
                chunk_len = len(header) + 2
            chunk.append(bullet)
            chunk_len += len(bullet) + 1
        if chunk:
            messages.append(header + "\n\n" + "\n".join(chunk))

    flush()

    if footer:
        if len(messages[-1]) + len(footer) <= split_limit:
            messages[-1] += footer
        else:
            messages.append(footer.strip())

    total_parts = len(messages)
    return [
        f"📬 <b>Tin mới</b> (phần {idx}/{total_parts})\n\n{msg}"
        for idx, msg in enumerate(messages, start=1)
    ]


def format_no_new_articles(now: datetime) -> str:
    return f"🟢 <b>NEWS MONITOR</b>\n\n{now.strftime('%H:%M')} — Không có tin mới."


def format_partial_failure_no_new(errored_sources: List[str], now: datetime) -> str:
    """Some sources failed this cycle and the sources that did succeed had
    nothing new. Must never read as "no new articles" (spec section 14) —
    the failure has to stay visible."""
    lines = [
        "⚠️ <b>NEWS MONITOR</b>",
        "",
        "Không có tin mới từ các nguồn hoạt động.",
        "",
        "<b>Nguồn lỗi:</b>",
    ]
    lines += [f"• {_esc(s)}" for s in errored_sources]
    lines += ["", f"⏰ {now.strftime('%d/%m/%Y %H:%M')}"]
    return "\n".join(lines)


def format_all_sources_failed(errored_sources: List[str], now: datetime) -> str:
    lines = ["🔴 <b>NEWS MONITOR</b>", "", "Không thể hoàn tất lượt quét.", "", "<b>Nguồn lỗi:</b>"]
    lines += [f"• {_esc(s)}" for s in errored_sources]
    lines += ["", f"⏰ {now.strftime('%d/%m/%Y %H:%M')}"]
    return "\n".join(lines)


def format_stale_sources_warning(
    stale: List[Tuple[str, datetime]], threshold_hours: int, now: datetime
) -> str:
    """V3 reliability: a source can crawl "successfully" (HTTP 200, no
    CrawlerError) while its feed has silently stopped changing — the
    real VietnamNet incident found during V2 audit, undetectable by
    the normal error-report path since nothing ever raises. `stale` is
    a list of (source_name, last_new_article_at) tuples."""
    lines = [
        "🩺 <b>NEWS MONITOR — Cảnh báo nguồn</b>",
        "",
        f"Các nguồn sau không có bài mới nào trong hơn {threshold_hours}h qua "
        "— có thể RSS đã hỏng hoặc đổi cấu trúc, nên kiểm tra lại:",
        "",
    ]
    for source, last_new in stale:
        lines.append(f"• {_esc(source)} (bài mới gần nhất: {last_new.strftime('%d/%m/%Y %H:%M')})")
    lines += ["", f"⏰ {now.strftime('%d/%m/%Y %H:%M')}"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------


def send_message(bot_token: str, chat_id: str, text: str, timeout: int, max_retries: int) -> None:
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    last_exc: Optional[Exception] = None
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, data=payload, timeout=timeout)
            try:
                data = resp.json()
            except ValueError:
                data = {}
            if resp.status_code == 200 and data.get("ok"):
                return
            raise TelegramError(f"HTTP {resp.status_code}: {data or resp.text[:200]}")
        except (requests.RequestException, TelegramError) as exc:
            last_exc = exc
            logger.warning(
                "Telegram send attempt %d/%d failed: %s", attempt, max_retries, exc
            )
            if attempt < max_retries:
                time.sleep(min(2**attempt, 10))

    raise TelegramError(
        f"Failed to send Telegram message after {max_retries} attempts: {last_exc}"
    )


def send_messages(
    bot_token: str, chat_id: str, texts: List[str], timeout: int, max_retries: int
) -> None:
    """Send multiple messages. All-or-nothing from the caller's point of
    view: if any message fails, this raises and the caller must not mark
    the underlying articles as sent (see module docstring)."""
    for text in texts:
        send_message(bot_token, chat_id, text, timeout, max_retries)

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

# Curated so recognizable sources get a fitting icon (VTV = television,
# Chính phủ = a government building, VietnamPlus = a "+"...) rather
# than arbitrary colors. A source not listed here (a new crawler added
# later, before this dict is updated) falls back to a small pool
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
    "VietnamPlus": "➕",
    "Nhân Dân": "⭐",
    "Chính phủ": "🏛️",
    "VTV": "📺",
    "VietnamBiz": "💱",
    "CafeBiz": "☕",
    "Đầu tư Chứng khoán": "📉",
    "Diễn đàn Doanh nghiệp": "🏢",
    "Báo Đầu tư": "💼",
    "FiLi": "🛡️",
}
_FALLBACK_ICONS = ["🟢", "🔶", "🔷", "🟩", "🟦", "🟧"]

# Reserve room for the "(phần N/M)" part header added to each message only
# when a cycle is large enough to need splitting (see format_grouped_articles)
# — comfortably covers up to 3-digit part counts.
_PART_HEADER_RESERVE = 48

# Rule-based "this might be a big story" flagging — no AI, just a
# curated list of urgency/magnitude phrases common in Vietnamese
# finance headlines, matched case-insensitively as a plain substring
# of the title. This exists because, without it, a market-moving
# headline from the 14th configured source lands at the very bottom
# of the message, visually identical to routine news above it — a
# user skimming on their phone can easily miss the one line that
# actually mattered. Tune this list from real false positives/
# negatives once running; it is deliberately conservative (phrases,
# not bare words like "tăng", which would flag almost everything).
HOT_KEYWORDS = [
    "khẩn cấp", "khủng hoảng", "sụp đổ", "sập sàn", "phá sản", "vỡ nợ",
    "vỡ trận", "tăng vọt", "giảm mạnh", "giảm sốc", "tăng sốc",
    "lao dốc", "rơi tự do", "kỷ lục", "bất ngờ tăng", "bất ngờ giảm",
    "đình chỉ", "thu hồi", "sa thải hàng loạt",
]


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
    """dd/mm HH:MM, not just HH:MM: some feeds (VTV in particular) keep
    weeks of archived items in one RSS response, so a single batch of
    "new" articles can span several different calendar days. Showing
    only the hour made same-looking times from different days appear
    in what looked like random order (they were correctly sorted by
    full date+time underneath — the date was just invisible)."""
    if item.published_at is None:
        return None
    return item.published_at.strftime("%d/%m %H:%M")


def _is_hot(title: str) -> bool:
    lowered = title.lower()
    return any(kw in lowered for kw in HOT_KEYWORDS)


def _article_line(item: NewsItem) -> str:
    link = f'<a href="{_esc(item.url)}">{_esc(item.title)}</a>'
    t = _time_str(item)
    return f"• {link} — {t}" if t else f"• {link}"


def _hot_line(source: str, item: NewsItem) -> str:
    """Like _article_line, but also names the source inline — hot
    items are pulled out of their normal per-source block, so that
    context would otherwise be lost."""
    link = f'<a href="{_esc(item.url)}">{_esc(item.title)}</a>'
    t = _time_str(item)
    tail = f" — {t}" if t else ""
    return f"{_icon_for(source)} {link}{tail} <i>({_esc(source)})</i>"


def _source_header(source: str, count: int) -> str:
    return f"{_icon_for(source)} <b>{_esc(source.upper())}</b> ({count} bài)"


def _source_block(source: str, items: List[NewsItem]) -> List[str]:
    lines = [_source_header(source, len(items)), ""]
    lines += [_article_line(i) for i in items]
    return lines


def _pack_bullets(header: str, bullets: List[str], limit: int) -> List[str]:
    """Split a too-large-for-one-message list of bullet lines under a
    single repeated `header` into as few messages as possible, never
    cutting a bullet in half. Used both for one source with an
    unusually large batch and for an oversized hot-news section."""
    messages: List[str] = []
    chunk: List[str] = []
    chunk_len = len(header) + 2
    for bullet in bullets:
        if chunk and chunk_len + len(bullet) + 1 > limit:
            messages.append(header + "\n\n" + "\n".join(chunk))
            chunk = []
            chunk_len = len(header) + 2
        chunk.append(bullet)
        chunk_len += len(bullet) + 1
    if chunk:
        messages.append(header + "\n\n" + "\n".join(chunk))
    return messages


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

    # Pull "hot" articles (matches HOT_KEYWORDS) out into a dedicated
    # top section regardless of which source or how deep in the
    # configured source order they'd otherwise land — a keyword match
    # from the last-configured source must not get buried under a
    # dozen blocks of routine news. Removed from their normal block
    # (not duplicated) so the message doesn't repeat itself.
    hot_pairs: List[Tuple[str, NewsItem]] = []
    normal_by_source: Dict[str, List[NewsItem]] = {}
    for s in sources:
        normal_items = []
        for item in items_by_source[s]:
            if _is_hot(item.title):
                hot_pairs.append((s, item))
            else:
                normal_items.append(item)
        if normal_items:
            normal_by_source[s] = normal_items
    normal_sources = list(normal_by_source.keys())

    hot_header = "🚨 <b>TIN NÓNG</b>"
    hot_lines = [hot_header, ""] + [_hot_line(s, i) for s, i in hot_pairs] if hot_pairs else []
    hot_block = "\n".join(hot_lines)

    blocks = {s: _source_block(s, normal_by_source[s]) for s in normal_sources}
    body_parts = ([hot_block] if hot_block else []) + [
        "\n".join(blocks[s]) for s in normal_sources
    ]
    full_text = f"{summary}\n\n" + "\n\n".join(body_parts) + footer
    if len(full_text) <= limit:
        return [full_text]

    # Pack whole blocks per message, reserving room for the "(phần
    # N/M)" header added to every message below; a single block (hot
    # section included) with so many articles that it alone exceeds
    # that reduced limit gets its bullet lines split across messages
    # instead, repeating its header.
    split_limit = limit - _PART_HEADER_RESERVE
    messages: List[str] = []
    def flush() -> None:
        if current:
            messages.append("\n".join(current))
            current.clear()

    if hot_pairs and len(hot_block) > split_limit:
        # The hot section itself is too big for one message — pack it
        # on its own (never silently dropped), `current` starts empty.
        current: List[str] = []
        messages.extend(_pack_bullets(hot_header, [_hot_line(s, i) for s, i in hot_pairs], split_limit))
    else:
        # The hot section always leads the first message — it's the
        # whole point of pulling it out — so it seeds `current` before
        # anything else is packed.
        current = list(hot_lines)

    for source in normal_sources:
        items = normal_by_source[source]
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
        messages.extend(_pack_bullets(header, bullets, split_limit))

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

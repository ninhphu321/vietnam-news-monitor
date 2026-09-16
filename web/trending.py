"""Trending-topics detection for the site's "🔥 Sự kiện nổi bật" panel.

No AI/ML/embeddings — per the project's stated scope, "sentiment/event
clustering" is explicitly not a goal (see README "Giới hạn đã biết").
Topics here are detected by literal keyword/phrase overlap across
article titles instead: a 2-3 word phrase that shows up in enough
DIFFERENT titles from enough DIFFERENT sources, recently, is treated
as "an event several outlets are covering right now".

This is a heuristic, not true semantic clustering: two articles about
the same real event with zero shared wording in their titles will
never be grouped. It works reasonably well here specifically because
Vietnamese financial headlines tend to spell out the same
company/bank/person name verbatim rather than paraphrase it — this
would need a real clustering approach (embeddings, an LLM pass) for
general-purpose news, which is deliberately out of scope.

HotScore (per user spec): each component is normalized 0-1 relative to
the strongest candidate in the current batch, then weighted:
    40% article_count   — số bài đề cập
    25% source_count    — số nguồn đề cập
    20% velocity        — tốc độ xuất hiện (bài/giờ kể từ lần đầu thấy)
    15% acceleration     — mức độ mới/tăng tốc (nhịp ra bài nửa sau so với nửa đầu)
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple

WINDOW_HOURS = 48
MIN_ARTICLES = 2
MIN_SOURCES = 2
TOP_N = 5
# A phrase used across too large a slice of the whole window is generic
# financial vocabulary ("Việt Nam", "chứng khoán", "ngân hàng", "đầu
# tư"...), not a specific event — verified against real production
# data on 2026-09-16, where exactly these ubiquitous terms otherwise
# swamped the top 5 by sheer volume despite naming no actual event.
# 3% was picked empirically: high enough that a real spike (dozens of
# articles on one specific story) still clears it, low enough to drop
# the every-day-vocabulary terms.
MAX_DOC_FREQ_RATIO = 0.03
# Floor for the cap above so it only engages once the window has real
# volume — with few articles total, 3% is a fraction of one article
# and would wrongly exclude everything, including genuinely narrow
# topics that just haven't accumulated much of an audience yet.
MIN_DOC_FREQ_CAP = 8

# Deliberately short: just common function words that would otherwise
# pollute every phrase. Not a full Vietnamese stopword list (that
# would need its own audit) — good enough for headline-style text
# where content words (entities, actions) already dominate.
_STOPWORDS = {
    "và", "của", "các", "một", "những", "để", "trong", "với", "là", "cho",
    "sau", "trước", "về", "này", "đã", "sẽ", "có", "không", "vẫn", "khi",
    "tại", "từ", "được", "bị", "vì", "do", "theo", "như", "nếu", "mà",
    "nên", "thì", "hay", "hoặc", "đến", "ra", "vào", "lên", "xuống",
    "còn", "cũng", "rất", "nhiều", "ít", "mới", "cũ", "đang", "đây",
    "đó", "ai", "gì", "sao", "thế", "nào", "bao", "giờ", "ngày",
    "tháng", "năm", "người", "việc", "cách", "phải", "cần", "chỉ",
    "chưa", "từng", "lại", "nữa", "thêm", "thôi", "đi", "lấy", "làm",
    "giữa", "trên", "dưới", "ngoài", "cùng", "hơn", "quá", "khá",
    "gần", "xa", "mỗi", "tất", "cả", "toàn", "bộ", "riêng", "chung",
    "khác", "tự", "mình", "họ", "ta", "tôi", "chúng",
    # Common headline verbs/fillers (added 2026-09-16 after real output
    # was dominated by phrases like "đề xuất", "tiếp tục", "hỗ trợ" —
    # generic action words that co-occur across totally unrelated
    # articles, same failure mode as a function word for this
    # purpose). Same "curated list, not AI" idiom as telegram.py's
    # HOT_KEYWORDS — expect to keep tuning this from real false
    # positives, same as that list.
    "đề", "xuất", "tiếp", "tục", "hỗ", "trợ", "dự", "kiến", "chuẩn",
    "thúc", "đẩy", "mắt", "khởi", "bố", "kỳ", "vọng", "triển", "khai",
    "quyết", "định", "yêu", "cầu", "kêu", "gọi", "xem", "xét", "nhận",
    "ghi", "đón", "duy", "trì", "giữ", "nguyên", "nâng", "cao", "tăng",
    "giảm", "mạnh", "sốc", "vọt", "sâu", "gồm", "gia", "hạn", "thương",
}

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# Multi-word financial/news vocabulary common enough to show up in a
# large fraction of ALL articles on ANY given day — these describe a
# beat, not an event, no matter how many sources/articles use them.
# Curated by hand (same "no AI, just a list" idiom as telegram.py's
# HOT_KEYWORDS) after finding these exact phrases swamping the top 5
# on real production data (2026-09-16) despite naming no actual story.
_GENERIC_PHRASES = {
    "ngân hàng", "chứng khoán", "doanh nghiệp", "đầu tư", "tài chính",
    "ngân sách", "giá trị", "thị trường", "nhà nước", "công ty",
    "cổ phiếu", "kinh tế", "việt nam", "lãi suất", "cổ đông",
    "giao dịch", "tăng trưởng", "vốn điều lệ", "tỷ usd", "triệu đồng",
    "bất động sản", "công nghệ", "trung tâm", "tỷ đồng", "triệu usd",
    "động sản", "tỷ giá", "chủ tịch", "tài sản", "bất động",
    "xây dựng", "nộp ngân sách",
}


@dataclass
class TrendingTopic:
    label: str
    score: float
    article_count: int
    source_count: int
    sources: List[str]
    sample_articles: List[dict] = field(default_factory=list)  # {"title","url","source"}


def _tokenize(title: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(title)]


def _content_words(title: str) -> List[str]:
    return [w for w in _tokenize(title) if w not in _STOPWORDS and len(w) > 1]


def _proper_noun_words(title: str) -> Set[str]:
    """Standalone words worth treating as their own candidate phrase:
    either an ALL-CAPS acronym/ticker of any length ("HĐQT", "SCIC",
    "EIB" — ordinary Vietnamese words are essentially never written
    this way), or a capitalized word at least 6 letters long. The
    length-6 bar (not just "any capitalized word") is what separates a
    real brand/entity name ("Eximbank", "Vietcombank", "Techcombank")
    from the first word of an ordinary capitalized phrase ("Trung" of
    "Trung Quốc", "Chứng" of "Chứng khoán", "Ngân" of "Ngân hàng") —
    those are common-word fragments, not names on their own, and
    without this bar they swamped real production output (2026-09-16)
    with nonsense single-word "topics". Not position-restricted:
    Vietnamese sentence-initial filler ("Một", "Nhiều", "Các",
    "Những"...) is already excluded by the stopword check, and a real
    entity opening a headline ("Eximbank gia hạn...") is common and
    must still be caught."""
    raw_tokens = _WORD_RE.findall(title)
    result = set()
    for tok in raw_tokens:
        lw = tok.lower()
        if lw in _STOPWORDS:
            continue
        is_acronym = len(tok) >= 2 and tok.isupper()
        is_named_entity = tok[:1].isupper() and len(tok) >= 6
        if is_acronym or is_named_entity:
            result.add(lw)
    return result


def _phrases(title: str) -> Set[str]:
    words = _content_words(title)
    result = set()
    for n in (2, 3):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i : i + n])
            if phrase not in _GENERIC_PHRASES:
                result.add(phrase)
    result |= _proper_noun_words(title)
    return result


def _group_by_phrase(articles: List[dict], now: datetime, window_hours: int) -> List[dict]:
    cutoff = now - timedelta(hours=window_hours)
    groups: Dict[str, dict] = {}
    windowed_count = 0
    for article in articles:
        ts = article["published_at"] or article["first_seen_at"]
        if ts is None or ts < cutoff or ts > now:
            continue
        windowed_count += 1
        for phrase in _phrases(article["title"]):
            g = groups.setdefault(
                phrase, {"phrase": phrase, "urls": set(), "sources": set(), "samples": []}
            )
            if article["url"] in g["urls"]:
                continue
            g["urls"].add(article["url"])
            g["sources"].add(article["source"])
            g["samples"].append(
                {"title": article["title"], "url": article["url"], "source": article["source"], "ts": ts}
            )

    max_doc_freq = max(windowed_count * MAX_DOC_FREQ_RATIO, MIN_DOC_FREQ_CAP)
    return [
        g for g in groups.values()
        if MIN_ARTICLES <= len(g["urls"]) <= max_doc_freq and len(g["sources"]) >= MIN_SOURCES
    ]


def _overlap_ratio(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _dedupe_overlapping(groups: List[dict]) -> List[dict]:
    """Drop a group that's essentially the same story as one already
    kept — e.g. a generic 2-word filler phrase riding along with a
    more distinctive one over nearly the same articles. Broader
    coverage (more articles) wins first, since that's the strongest
    evidence of what the group is really about; word count (more
    specific phrasing) is only the tiebreaker when coverage is equal —
    a single-word entity like "eximbank" mentioned across 3 articles
    should win over an incidental 2-word phrase 2 of those 3 also
    happen to share."""
    ordered = sorted(groups, key=lambda g: (-len(g["urls"]), -g["phrase"].count(" ")))
    accepted: List[dict] = []
    for g in ordered:
        if any(_overlap_ratio(g["urls"], acc["urls"]) >= 0.7 for acc in accepted):
            continue
        accepted.append(g)
    return accepted


def _score_groups(groups: List[dict], now: datetime) -> List[Tuple[dict, float]]:
    if not groups:
        return []

    def hours_ago(dt: datetime) -> float:
        return (now - dt).total_seconds() / 3600

    metrics = []
    for g in groups:
        timestamps = [s["ts"] for s in g["samples"]]
        article_count = len(g["urls"])
        source_count = len(g["sources"])

        first_seen = min(timestamps)
        age_hours = max(hours_ago(first_seen), 0.5)  # floor: avoid a brand-new topic exploding velocity
        velocity = article_count / age_hours

        # Acceleration: rate in the most recent quarter of the topic's
        # own lifespan vs. the rate before that — a topic still in its
        # first quarter-life (no "earlier" half yet) counts as
        # accelerating (2x) rather than undefined.
        span = now - first_seen
        recent_cutoff = now - span / 4
        recent = [t for t in timestamps if t >= recent_cutoff]
        earlier = [t for t in timestamps if t < recent_cutoff]
        recent_hours = max(hours_ago(recent_cutoff), 0.25)
        earlier_hours = max((recent_cutoff - first_seen).total_seconds() / 3600, 0.25)
        recent_rate = len(recent) / recent_hours
        earlier_rate = (len(earlier) / earlier_hours) if earlier else 0.0
        acceleration = min(recent_rate / earlier_rate, 5.0) if earlier_rate > 0 else (2.0 if recent else 0.0)

        metrics.append(
            {"group": g, "article_count": article_count, "source_count": source_count,
             "velocity": velocity, "acceleration": acceleration}
        )

    max_articles = max(m["article_count"] for m in metrics) or 1
    max_sources = max(m["source_count"] for m in metrics) or 1
    max_velocity = max(m["velocity"] for m in metrics) or 1
    max_accel = max(m["acceleration"] for m in metrics) or 1

    scored = []
    for m in metrics:
        score = (
            0.40 * (m["article_count"] / max_articles)
            + 0.25 * (m["source_count"] / max_sources)
            + 0.20 * (m["velocity"] / max_velocity)
            + 0.15 * (m["acceleration"] / max_accel)
        ) * 100
        scored.append((m["group"], round(score, 1)))
    return scored


def _display_label(phrase: str, sample_titles: List[str]) -> str:
    """Recover the original capitalization from a real title (Vietnamese
    proper nouns are usually capitalized in headlines) instead of a
    naive/wrong str.title() over every word."""
    words = phrase.split(" ")
    pattern = re.compile(r"\b" + r"\W+".join(re.escape(w) for w in words) + r"\b", re.IGNORECASE)
    for title in sample_titles:
        match = pattern.search(title)
        if match:
            return match.group(0)
    return phrase.title()


def top_trending(
    articles: List[dict], now: datetime, limit: int = TOP_N, window_hours: int = WINDOW_HOURS
) -> List[TrendingTopic]:
    groups = _group_by_phrase(articles, now, window_hours)
    groups = _dedupe_overlapping(groups)
    scored = _score_groups(groups, now)
    scored.sort(key=lambda pair: pair[1], reverse=True)

    topics = []
    for g, score in scored[:limit]:
        sample_titles = [s["title"] for s in g["samples"]]
        newest_samples = sorted(g["samples"], key=lambda s: s["ts"], reverse=True)[:3]
        topics.append(
            TrendingTopic(
                label=_display_label(g["phrase"], sample_titles),
                score=score,
                article_count=len(g["urls"]),
                source_count=len(g["sources"]),
                sources=sorted(g["sources"]),
                sample_articles=[
                    {"title": s["title"], "url": s["url"], "source": s["source"]} for s in newest_samples
                ],
            )
        )
    return topics

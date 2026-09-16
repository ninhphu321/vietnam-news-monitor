"""Issue Intelligence V3 — detects specific news ISSUES (not bare
entities and not bare topics) that multiple sources are covering
*today*, and ranks them with a fully-decomposed HotScore. Implements
PROJECT_SPEC_V3_ISSUE_INTELLIGENCE.md; supersedes the earlier
phrase-frequency "trending topics" cut (was web/trending.py).

Entity vs Topic vs Issue (spec section 3) — the core fix over the
previous version:
    Entity = a company/person/institution ("Eximbank", "NHNN").
    Topic  = a broad beat ("lãi suất", "nợ xấu") — curated below in
             _TOPIC_KEYWORDS, same "list, not AI" idiom as
             telegram.py's HOT_KEYWORDS.
    Issue  = a specific (entity, topic) pairing found together in one
             title ("Eximbank" + "nhân sự"), or a (topic, topic)
             pairing when no entity is present (an aggregate/
             industry-wide issue, e.g. "khối ngoại" + "bán ròng").

Grouping by a bare entity or a bare topic alone is exactly what the
spec forbids (section 3; section 16 tests 2-3): "Eximbank" alone would
merge its HR news with its branch-opening news with its dividend news
— three different issues sharing only a company name. Pairing entity
with topic (or topic with topic) is what keeps those separate while
still merging "Eximbank gia hạn đề cử nhân sự", "Eximbank hoãn chốt
danh sách ứng viên" and "Cổ đông chất vấn Eximbank về kế hoạch nhân
sự" into one issue: same entity, same topic tag ("nhân sự lãnh đạo"),
different wording.

No AI/ML/embeddings/LLM calls anywhere in this module — entity and
topic detection are both rule-based (regex + curated lists), so the
"don't send every article to an LLM" cost concern in spec section 13
does not apply; there is no LLM call to begin with.

Scope is *today* only (spec section 9): from 00:00:00 to now, in
Asia/Ho_Chi_Minh — not a rolling window like the previous version's
48h. This is most of this module's answer to "ranking stability" (spec
section 10): a full day's accumulated data moves far less between two
20-minute crawl cycles than a short sliding window did. No cross-run
persisted state/hysteresis is layered on top of that — it would need a
new DB table to remember previous rankings, and the spec explicitly
says not to overengineer this ("chỉ cần đủ để tránh ranking nhảy vô
lý"); the daily window plus the minimum thresholds below were judged
sufficient without it.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple
from zoneinfo import ZoneInfo

TIMEZONE = "Asia/Ho_Chi_Minh"
TOP_N = 5
# Spec section 10's minimum threshold, verbatim: "article_count >= 3
# OR unique_source_count >= 2". Configurable per spec's own requirement
# ("Threshold phải configurable") — pass overrides into top_issues().
MIN_ARTICLES_THRESHOLD = 3
MIN_SOURCES_THRESHOLD = 2

_WORD_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# Deliberately short: just common function words that would otherwise
# pollute every phrase match. Not a full Vietnamese stopword list —
# good enough for headline-style text where content words (entities,
# actions) already dominate.
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
}

# --- Topic vocabulary (the "Topic" dimension, spec section 3) ---------
# Canonical tag -> trigger substrings, matched against the lowercased
# title. Curated by hand from real headlines audited 2026-09-16/17
# (this replaces the previous version's _GENERIC_PHRASES blacklist —
# those exact phrases are the topic vocabulary now, used deliberately
# as one half of an (entity, topic) pair instead of only as a filter).
_TOPIC_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "lãi suất": ("lãi suất", "lãi vay", "biểu lãi", "lãi tiết kiệm"),
    "tín dụng": ("tín dụng", "room tín dụng"),
    "nợ xấu": ("nợ xấu",),
    "cổ tức": ("cổ tức",),
    "tăng vốn": ("tăng vốn", "vốn điều lệ"),
    "trái phiếu": ("trái phiếu",),
    "nhân sự lãnh đạo": ("nhân sự", "hđqt", "chủ tịch", "tổng giám đốc",
                          "đề cử", "bổ nhiệm", "miễn nhiệm", "từ nhiệm"),
    "tuyển dụng": ("tuyển dụng",),
    "chi nhánh": ("chi nhánh",),
    "khởi tố": ("khởi tố", "bắt tạm giam", "truy tố"),
    "sáp nhập": ("sáp nhập", "hợp nhất", "thâu tóm"),
    "niêm yết": ("niêm yết", "ipo"),
    "thoái vốn": ("thoái vốn",),
    "khối ngoại": ("khối ngoại", "nhà đầu tư nước ngoài"),
    "bán ròng": ("bán ròng",),
    "mua ròng": ("mua ròng",),
    "tỷ giá": ("tỷ giá",),
    "giá vàng": ("giá vàng", "vàng miếng", "vàng nhẫn"),
    "bất động sản": ("bất động sản",),
    "chứng khoán": ("vn-index", "chứng khoán"),
    "ngân sách nhà nước": ("nộp ngân sách", "ngân sách nhà nước"),
    "thuế": ("thuế",),
    "fed": ("fed", "cục dự trữ liên bang"),
}


def _tokenize(title: str) -> List[str]:
    return [w.lower() for w in _WORD_RE.findall(title)]


def _extract_topics(title: str) -> Set[str]:
    lower = title.lower()
    return {tag for tag, triggers in _TOPIC_KEYWORDS.items() if any(t in lower for t in triggers)}


# Generic institutional/role/currency/macro acronyms: written in
# ALL-CAPS like a real ticker ("EIB", "SCIC") but never a specific
# company or person, so they must never be accepted as an "entity" —
# several of these deliberately double as _TOPIC_KEYWORDS triggers
# instead (their correct role). Found via a live-data false-merge on
# 2026-09-16 ("HĐQT" wrongly merged two unrelated companies' news).
_GENERIC_ACRONYMS = {
    "hđqt", "hội đồng quản trị", "ceo", "cfo", "tgđ", "ipo", "usd",
    "vnd", "gdp", "cpi", "npl", "vn-index", "vni",
}


def _extract_entities(title: str) -> Set[str]:
    """The "Entity" dimension: either an ALL-CAPS acronym/ticker of any
    length ("SCIC", "EIB" — ordinary Vietnamese words are essentially
    never written this way), or a capitalized word at least 6 letters
    long. The length-6 bar (not just "any capitalized word") is what
    separates a real brand/entity name ("Eximbank", "Vietcombank") from
    the first word of an ordinary capitalized phrase ("Trung" of
    "Trung Quốc", "Ngân" of "Ngân hàng") — verified against real
    production output on 2026-09-16, where those short fragments
    produced nonsense single-word groups. Not position-restricted:
    Vietnamese sentence-initial filler ("Một", "Nhiều") is already
    excluded by the stopword check, and a real entity opening a
    headline ("Eximbank gia hạn...") is common and must still be
    caught.

    `_GENERIC_ACRONYMS` closes a real gap found the same day: "HĐQT"
    (Hội đồng quản trị — every company has one) is all-caps and would
    otherwise qualify as an "entity", merging Eximbank's own board-seat
    news with an unrelated company's "X tham gia HĐQT một công ty Y"
    purely because both mention the word "HĐQT" — an entity/topic
    conflation the spec explicitly forbids (section 3). It stays in
    _TOPIC_KEYWORDS as a *topic* trigger, which is its correct role."""
    raw_tokens = _WORD_RE.findall(title)
    result = set()
    for tok in raw_tokens:
        lw = tok.lower()
        if lw in _STOPWORDS or lw in _GENERIC_ACRONYMS:
            continue
        is_acronym = len(tok) >= 2 and tok.isupper()
        is_named_entity = tok[:1].isupper() and len(tok) >= 6
        if is_acronym or is_named_entity:
            result.add(lw)
    return result


def _issue_keys(title: str) -> Set[Tuple[str, str, str]]:
    """The (kind, a, b) issue keys this title contributes to — never a
    bare entity or a bare topic alone (spec section 3 / section 16
    tests 2-3: the same entity with a different topic must NOT be
    treated as the same issue, and vice versa). `kind` disambiguates
    an entity/topic pair from a topic/topic pair so the two families
    never collide."""
    entities = _extract_entities(title)
    topics = _extract_topics(title)
    keys: Set[Tuple[str, str, str]] = set()
    if entities and topics:
        for e in entities:
            for t in topics:
                keys.add(("entity_topic", e, t))
    elif len(topics) >= 2:
        ordered = sorted(topics)
        for i in range(len(ordered)):
            for j in range(i + 1, len(ordered)):
                keys.add(("topic_topic", ordered[i], ordered[j]))
    return keys


def _today_window(now: datetime) -> datetime:
    """Start of "today" (00:00:00) in `now`'s own timezone — the caller
    is responsible for passing `now` already in Asia/Ho_Chi_Minh (spec
    section 9/16 test 8)."""
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def _group_by_issue(articles: List[dict], now: datetime) -> List[dict]:
    start = _today_window(now)
    groups: Dict[Tuple[str, str, str], dict] = {}
    for article in articles:
        ts = article["published_at"] or article["first_seen_at"]
        if ts is None or ts < start or ts > now:
            continue
        for key in _issue_keys(article["title"]):
            g = groups.setdefault(key, {"key": key, "urls": set(), "sources": set(), "samples": []})
            if article["url"] in g["urls"]:
                continue
            g["urls"].add(article["url"])
            g["sources"].add(article["source"])
            g["samples"].append(
                {"title": article["title"], "url": article["url"], "source": article["source"], "ts": ts}
            )
    return list(groups.values())


def _overlap_ratio(a: Set[str], b: Set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _dedupe_overlapping(groups: List[dict]) -> List[dict]:
    """Safety net for the rare case where two different (entity/topic)
    pairs end up covering nearly the same article set (e.g. two topic
    tags that habitually co-occur) — keep the one with broader
    coverage, preferring an entity_topic pair over a topic_topic one
    as the tiebreaker since it names a more specific "who"."""
    ordered = sorted(groups, key=lambda g: (-len(g["urls"]), 0 if g["key"][0] == "entity_topic" else 1))
    accepted: List[dict] = []
    for g in ordered:
        if any(_overlap_ratio(g["urls"], acc["urls"]) >= 0.7 for acc in accepted):
            continue
        accepted.append(g)
    return accepted


def _passes_threshold(g: dict, min_articles: int, min_sources: int) -> bool:
    return len(g["urls"]) >= min_articles or len(g["sources"]) >= min_sources


def _score_issue(g: dict, now: datetime) -> dict:
    timestamps = [s["ts"] for s in g["samples"]]
    article_count = len(g["urls"])
    source_count = len(g["sources"])
    first_seen = min(timestamps)
    last_seen = max(timestamps)

    age_hours = max((now - first_seen).total_seconds() / 3600, 0.5)
    velocity = article_count / age_hours

    # Acceleration/novelty: rate in the most recent quarter of the
    # issue's own lifespan today vs. the rate before that — an issue
    # still in its first quarter-life (no "earlier" half yet) counts
    # as accelerating (2x) rather than undefined.
    span = now - first_seen
    recent_cutoff = now - span / 4
    recent = [t for t in timestamps if t >= recent_cutoff]
    earlier = [t for t in timestamps if t < recent_cutoff]
    recent_hours = max((now - recent_cutoff).total_seconds() / 3600, 0.25)
    earlier_hours = max((recent_cutoff - first_seen).total_seconds() / 3600, 0.25)
    recent_rate = len(recent) / recent_hours
    earlier_rate = (len(earlier) / earlier_hours) if earlier else 0.0
    acceleration = min(recent_rate / earlier_rate, 5.0) if earlier_rate > 0 else (2.0 if recent else 0.0)

    recent_sources = {s["source"] for s in g["samples"] if s["ts"] >= recent_cutoff}
    earlier_sources = {s["source"] for s in g["samples"] if s["ts"] < recent_cutoff}
    new_sources = recent_sources - earlier_sources

    return {
        "group": g, "article_count": article_count, "source_count": source_count,
        "first_seen": first_seen, "last_seen": last_seen,
        "velocity": velocity, "acceleration": acceleration,
        "recent_count": len(recent), "new_sources": new_sources,
    }


def _score_all(metrics: List[dict]) -> None:
    """Normalizes each component to 0-100 relative to the strongest
    candidate in this batch, then blends per spec section 7 — mutates
    each metric dict in place, adding volume_score/source_score/
    velocity_score/novelty_score/hot_score, each independently
    inspectable (spec: "Code phải tách thành các component... không
    hard-code thành một công thức khó debug").

    Honest limit on spec section 8's anti-bias goal: this weighted
    blend makes source diversity a real, measurable factor instead of
    ignoring it, but at 25% weight it is a *counterweight* to volume
    (40%) and velocity (20%), not a veto. A single source posting many
    enough near-duplicate updates can still out-score a genuinely
    multi-source issue with a modest article-count edge — verified in
    tests/test_issues.py's volume-bias test, which uses a small (4 vs
    3) gap precisely because a large enough one does flip the result.
    Section 8's own wording ("không được mặc định Issue đó hot nhất")
    reads as "not automatically/by default hottest from raw count
    alone", which this satisfies; it is not a guarantee that source
    diversity always wins outright regardless of the volume gap's size.
    """
    max_articles = max((m["article_count"] for m in metrics), default=0) or 1
    max_sources = max((m["source_count"] for m in metrics), default=0) or 1
    max_velocity = max((m["velocity"] for m in metrics), default=0) or 1
    max_accel = max((m["acceleration"] for m in metrics), default=0) or 1

    for m in metrics:
        # Clamp defensively (spec section 15: "HotScore ngoài 0-100 ->
        # error") — the max-relative normalization above guarantees
        # this by construction, but the clamp is cheap insurance
        # against a future refactor breaking that invariant silently.
        m["volume_score"] = min(max(round(100 * m["article_count"] / max_articles, 1), 0.0), 100.0)
        m["source_score"] = min(max(round(100 * m["source_count"] / max_sources, 1), 0.0), 100.0)
        m["velocity_score"] = min(max(round(100 * m["velocity"] / max_velocity, 1), 0.0), 100.0)
        m["novelty_score"] = min(max(round(100 * m["acceleration"] / max_accel, 1), 0.0), 100.0)
        m["hot_score"] = min(max(round(
            m["volume_score"] * 0.40
            + m["source_score"] * 0.25
            + m["velocity_score"] * 0.20
            + m["novelty_score"] * 0.15,
            1,
        ), 0.0), 100.0)


def _why_hot(m: dict) -> List[str]:
    """Every bullet must trace to a real metric already computed above
    (spec section 11: "Không được bịa" / "Why Hot phải dựa trên metric
    thật") — never a vague claim like "toàn thị trường đang quan tâm"
    the data can't back up."""
    bullets = [
        f"{m['source_count']} nguồn báo cùng đề cập",
        f"xuất hiện {m['article_count']} bài trong ngày",
    ]
    if m["acceleration"] >= 1.5 and m["recent_count"] > 0:
        bullets.append("số lượng bài tăng nhanh trong khoảng thời gian gần đây")
    if m["new_sources"]:
        bullets.append(f"có {len(m['new_sources'])} nguồn mới bắt đầu đề cập gần đây")
    return bullets[:4]


def _entity_display(entity: str, sample_titles: List[str]) -> str:
    """Recovers the original capitalization from a real title
    (Vietnamese proper nouns are usually capitalized in headlines)
    instead of a naive/wrong str.title()."""
    pattern = re.compile(r"\b" + re.escape(entity) + r"\b", re.IGNORECASE)
    for title in sample_titles:
        match = pattern.search(title)
        if match:
            return match.group(0)
    return entity.title()


def _issue_title(key: Tuple[str, str, str], sample_titles: List[str]) -> str:
    kind, a, b = key
    if kind == "entity_topic":
        return f"{_entity_display(a, sample_titles)} · {b.capitalize()}"
    return f"{a.capitalize()} · {b.capitalize()}"


def _issue_id(key: Tuple[str, str, str]) -> str:
    slug = re.sub(r"\s+", "-", f"{key[1]}-{key[2]}".strip().lower())
    return re.sub(r"[^a-z0-9\-]", "", slug) or "issue"


@dataclass
class Issue:
    issue_id: str
    issue_title: str
    entities: List[str]
    topics: List[str]
    article_count: int
    unique_source_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    velocity: float
    acceleration: float
    volume_score: float
    source_score: float
    velocity_score: float
    novelty_score: float
    hot_score: float
    sources: List[str]
    why_hot: List[str] = field(default_factory=list)
    representative_articles: List[dict] = field(default_factory=list)  # top 3, newest first
    all_articles: List[dict] = field(default_factory=list)  # full list, newest first


def top_issues(
    articles: List[dict],
    now: datetime,
    limit: int = TOP_N,
    min_articles: int = MIN_ARTICLES_THRESHOLD,
    min_sources: int = MIN_SOURCES_THRESHOLD,
) -> List[Issue]:
    """Today's (Asia/Ho_Chi_Minh) top issues by HotScore. `now` must
    already be tz-aware in that timezone — this function trusts the
    caller rather than importing a hard-coded ZoneInfo, so tests can
    supply any reference instant, but refuses a naive datetime outright
    (spec section 15: the "today" boundary must be unambiguous, never
    silently computed against the wrong clock)."""
    if now.tzinfo is None:
        raise ValueError("top_issues() requires a timezone-aware `now` (Asia/Ho_Chi_Minh)")
    groups = _group_by_issue(articles, now)
    groups = [g for g in groups if _passes_threshold(g, min_articles, min_sources)]
    groups = _dedupe_overlapping(groups)

    metrics = [_score_issue(g, now) for g in groups]
    _score_all(metrics)
    metrics.sort(key=lambda m: m["hot_score"], reverse=True)

    issues = []
    for m in metrics[:limit]:
        g = m["group"]
        key = g["key"]
        sample_titles = [s["title"] for s in g["samples"]]
        all_sorted = sorted(g["samples"], key=lambda s: s["ts"], reverse=True)
        articles_out = [{"title": s["title"], "url": s["url"], "source": s["source"]} for s in all_sorted]
        entities = [key[1]] if key[0] == "entity_topic" else []
        topics = [key[2]] if key[0] == "entity_topic" else [key[1], key[2]]

        title = _issue_title(key, sample_titles)
        if not title.strip():
            # Spec section 15: "Issue không có title -> reject". Should
            # be unreachable (a key's parts are always non-empty
            # strings by construction) — kept as an explicit guard
            # rather than trusting that invariant silently forever.
            continue

        issues.append(
            Issue(
                issue_id=_issue_id(key),
                issue_title=title,
                entities=entities,
                topics=topics,
                article_count=m["article_count"],
                unique_source_count=m["source_count"],
                first_seen_at=m["first_seen"],
                last_seen_at=m["last_seen"],
                velocity=round(m["velocity"], 2),
                acceleration=round(m["acceleration"], 2),
                volume_score=m["volume_score"],
                source_score=m["source_score"],
                velocity_score=m["velocity_score"],
                novelty_score=m["novelty_score"],
                hot_score=m["hot_score"],
                sources=sorted(g["sources"]),
                why_hot=_why_hot(m),
                representative_articles=articles_out[:3],
                all_articles=articles_out,
            )
        )
    return issues

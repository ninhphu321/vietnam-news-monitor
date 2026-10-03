"""Financial Information Intelligence, phase 1 (roadmap V6 §48-56): turns
Top Issues into *Information Events* with an evidence structure, and
builds the Daily Briefing.

    ENTITY -> EVENT -> MEDIA COVERAGE -> SOURCE DIVERSITY -> SIGNAL

An Information Event is not a new store: it is a derived view of an Issue
(web/issues.py already pairs an entity with a topic from the title) plus
what kind of sources covered it. Computed on demand each build, like
Velocity and the diff — roadmap §54's events/event_sources tables are
deliberately not created (see TONG-QUAN-DU-AN.md mục 20).

Hard limits, straight from the roadmap and kept visible in the UI wording:
  - "Evidence", never "truth score" (§52): this reports WHO covered an
    event and in what order, nothing about whether it is correct.
  - No prediction (§53): a signal type never implies a price direction.
  - Title-only data: "no official source detected" means no *matching
    title* from a configured official source, not that none exists.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Sequence

from web.issues import Issue
from web.signals import ACCELERATING, EMERGING
from web.source_registry import MEDIA, OFFICIAL, type_for

# §53 signal types. Only these two can occur until real regulatory /
# market / macro crawlers exist (source types beyond MEDIA/OFFICIAL).
MEDIA_SIGNAL = "MEDIA_SIGNAL"
OFFICIAL_SIGNAL = "OFFICIAL_SIGNAL"

_SEPARATOR = " · "


@dataclass
class Evidence:
    """§52 "Information Evidence"."""

    official_sources: List[str]
    media_sources: List[str]
    first_report_source: Optional[str]      # first MEDIA article's outlet
    first_report_at: Optional[datetime]
    first_official_at: Optional[datetime] = None

    @property
    def has_official(self) -> bool:
        return bool(self.official_sources)


@dataclass
class InformationEvent:
    issue_id: str
    title: str
    entity: Optional[str]                   # display name, None for topic-only issues
    event_type: str                         # the topic half, e.g. "Nhân sự lãnh đạo"
    evidence: Evidence
    signal_types: List[str]
    high_attention: bool                    # official source present AND media accelerating (§53)
    lifecycle_status: Optional[str]
    issue: Issue = field(repr=False, default=None)


def _split_title(issue: Issue):
    """"Eximbank · Nhân sự lãnh đạo" -> ("Eximbank", "Nhân sự lãnh đạo");
    a topic-only issue ("Khối ngoại · Mua ròng") has no entity."""
    if issue.entities and _SEPARATOR in issue.issue_title:
        entity, _, topic = issue.issue_title.partition(_SEPARATOR)
        return entity, topic
    return None, issue.issue_title


def evidence_for(issue: Issue, registry: Dict[str, dict]) -> Evidence:
    official = sorted({s for s in issue.sources if type_for(s, registry) == OFFICIAL})
    media = sorted({s for s in issue.sources if type_for(s, registry) == MEDIA})
    first_media = first_official = None
    for a in issue.all_articles:
        ts = a.get("ts")
        if ts is None:
            continue
        kind = type_for(a["source"], registry)
        if kind == MEDIA and (first_media is None or ts < first_media[0]):
            first_media = (ts, a["source"])
        elif kind == OFFICIAL and (first_official is None or ts < first_official):
            first_official = ts
    return Evidence(
        official_sources=official, media_sources=media,
        first_report_source=first_media[1] if first_media else None,
        first_report_at=first_media[0] if first_media else None,
        first_official_at=first_official,
    )


def _media_accelerating(issue: Issue, lifecycle_status: Optional[str]) -> bool:
    if lifecycle_status == ACCELERATING:
        return True
    v = issue.velocity_1h
    return v is not None and v.status == ACCELERATING


def build_event(issue: Issue, registry: Dict[str, dict], lifecycle_status: Optional[str] = None) -> InformationEvent:
    ev = evidence_for(issue, registry)
    kinds = []
    if ev.official_sources:
        kinds.append(OFFICIAL_SIGNAL)
    if ev.media_sources:
        kinds.append(MEDIA_SIGNAL)
    entity, topic = _split_title(issue)
    return InformationEvent(
        issue_id=issue.issue_id, title=issue.issue_title, entity=entity, event_type=topic,
        evidence=ev, signal_types=kinds,
        # §53: official information + accelerating media coverage = high
        # attention. Says nothing about what the stock/market will do.
        high_attention=ev.has_official and _media_accelerating(issue, lifecycle_status),
        lifecycle_status=lifecycle_status, issue=issue,
    )


def build_events(
    issues: Sequence[Issue], registry: Dict[str, dict], lifecycle_by_id: Optional[Dict[str, str]] = None,
) -> List[InformationEvent]:
    lifecycle_by_id = lifecycle_by_id or {}
    return [build_event(i, registry, lifecycle_by_id.get(i.issue_id)) for i in issues]


# ------------------------------------------------------------ daily briefing §56
@dataclass
class BriefingItem:
    key: str
    heading: str
    event: Optional[InformationEvent]       # None -> nothing qualifies today
    empty_note: str


def _known_entities(history_rows: Sequence[dict], today: date) -> Optional[set]:
    """Entity names seen in any Top-5 issue BEFORE today, or None when
    there is no earlier history at all (then "new" cannot be judged)."""
    earlier = [r for r in history_rows if r["day"] < today.isoformat()]
    if not earlier:
        return None
    return {r["title"].partition(_SEPARATOR)[0].strip().lower() for r in earlier if _SEPARATOR in r["title"]}


def build_briefing(events: Sequence[InformationEvent], history_rows: Sequence[dict], today: date) -> List[BriefingItem]:
    """The five fixed slots of roadmap §56. A slot with no qualifying
    event says so instead of being padded with something weaker."""
    def pick(candidates, key):
        return max(candidates, key=key) if candidates else None

    def hot(e):
        return e.issue.hot_score

    emerging = [e for e in events if e.lifecycle_status == EMERGING]
    accelerating = [e for e in events if e.lifecycle_status == ACCELERATING
                    or (e.issue.velocity_1h is not None and e.issue.velocity_1h.status == ACCELERATING)]
    known = _known_entities(history_rows, today)
    new_entity = [e for e in events if e.entity and known is not None and e.entity.lower() not in known]
    official = [e for e in events if e.evidence.has_official]

    return [
        BriefingItem("emerging", "Sự kiện mới nổi đáng chú ý", pick(emerging, hot),
                     "Chưa có sự kiện nào mới xuất hiện trong Top Issues hôm nay."),
        BriefingItem("accelerating", "Vấn đề tăng tốc nhanh nhất",
                     pick(accelerating, lambda e: (e.issue.velocity_1h.acceleration if e.issue.velocity_1h else 0, hot(e))),
                     "Hiện không có vấn đề nào đang tăng tốc."),
        BriefingItem("broadest", "Được nhiều nguồn đưa tin nhất",
                     pick(list(events), lambda e: (e.issue.unique_source_count, hot(e))),
                     "Chưa có issue nào đủ ngưỡng hôm nay."),
        BriefingItem("new_entity", "Tín hiệu từ đối tượng mới",
                     pick(new_entity, hot),
                     "Chưa đủ lịch sử các ngày trước để biết đối tượng nào là mới." if known is None
                     else "Không có đối tượng nào mới xuất hiện so với các ngày trước."),
        BriefingItem("official", "Tín hiệu từ nguồn chính thống", pick(official, hot),
                     "Chưa phát hiện tiêu đề khớp từ nguồn chính thống nào đang theo dõi."),
    ]

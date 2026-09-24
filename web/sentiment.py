"""Rule-based headline tone for finance/banking news — no AI.

Every label comes with the exact keywords that produced it, so a person
can see (and disagree with) why a headline was tagged. It is an ESTIMATE
from the headline alone: expect errors on irony, quotes and headlines
that only hint at the story. Treat "tiêu cực" as "worth a look", never as
a verdict.

Keyword weights:
    critical  -3   events that are crises by themselves (khởi tố, vỡ nợ,
                   rút tiền ồ ạt, kiểm soát đặc biệt, ...)
    strong    -2   clearly bad for a bank's reputation (tin đồn, bị phạt,
                   rò rỉ, thua lỗ, ...)
    mild      -1   negative-leaning but often neutral analysis
                   (nợ xấu, cảnh báo, rủi ro, ...)
    positive  +1 / +2

Only strong and critical keywords count toward crisis alerts (see
web/brandwatch.py) — mild ones colour the tone breakdown but never page
anyone.

Denial: a headline that DENIES a rumour ("bác bỏ tin đồn", "đính chính",
"khẳng định không ...") is the bank's own reassurance, not fresh bad news;
its negative keywords are ignored and it is labelled neutral.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

CRITICAL = [
    "khởi tố", "bắt tạm giam", "bị bắt", "vỡ nợ", "phá sản", "mất khả năng thanh toán",
    "rút tiền ồ ạt", "đổ xô rút tiền", "kiểm soát đặc biệt", "sụp đổ", "căng thẳng thanh khoản",
    "thanh khoản căng", "truy nã",
]
STRONG = [
    "tin đồn", "đồn thổi", "rò rỉ", "tấn công mạng", "sự cố", "bị phạt", "xử phạt", "vi phạm",
    "thanh tra", "bị điều tra", "thua lỗ", "báo lỗ", "lỗ ròng", "sa thải", "hạ xếp hạng", "hạ điểm tín nhiệm",
    "thu hồi giấy phép", "bị thu hồi", "đình chỉ", "khởi kiện", "bị kiện", "tố cáo", "bê bối", "sai phạm", "thất thoát",
    "mất tiền", "lừa đảo", "hack", "nợ xấu tăng", "nợ xấu tăng vọt", "bị khoá", "ngừng giao dịch",
]
MILD = [
    "nợ xấu", "giảm mạnh", "sụt giảm", "lao dốc", "giảm sâu", "cảnh báo", "áp lực", "rủi ro",
    "khó khăn", "nghi vấn", "chậm trễ", "đóng cửa", "cắt giảm",
]
POSITIVE_STRONG = [
    "lợi nhuận kỷ lục", "lãi kỷ lục", "vinh danh", "đạt giải", "giải thưởng", "tăng hạng",
    "nâng hạng", "bứt phá", "tăng trưởng mạnh",
]
POSITIVE_MILD = [
    "tăng vốn", "chia cổ tức", "ra mắt", "hợp tác", "ký kết", "tài trợ", "đồng hành",
    "lợi nhuận tăng", "tăng trưởng", "huy động thành công", "lãi tăng", "mở rộng",
]
DENIAL = ["bác bỏ", "phủ nhận", "đính chính", "khẳng định không", "không có chuyện", "không đúng sự thật",
          "khẳng định an toàn", "trấn an"]

# Headlines describing a bank's own protection/anti-fraud effort mention
# scam words ("lừa đảo", "cảnh báo", "rò rỉ") without being bad news about
# the bank — e.g. "SHB mở rộng tính năng cảnh báo lừa đảo". Like a denial,
# they neutralise non-critical negative keywords (critical ones such as
# "khởi tố" still count).
PROTECTIVE = ["ngăn chặn", "phòng chống", "phòng ngừa", "chống lừa đảo", "bảo vệ", "tính năng cảnh báo",
              "bảo mật", "tăng cường an ninh", "nhận diện gian lận"]

NEGATIVE, POSITIVE, NEUTRAL = "tiêu cực", "tích cực", "trung tính"


def _compile(words: List[str]) -> List[Tuple[str, re.Pattern]]:
    return [(w, re.compile(rf"(?<!\w){re.escape(w)}(?!\w)")) for w in words]


_TIERS: Dict[str, Tuple[int, List[Tuple[str, re.Pattern]]]] = {
    "critical": (-3, _compile(CRITICAL)),
    "strong": (-2, _compile(STRONG)),
    "mild": (-1, _compile(MILD)),
    "pos_strong": (2, _compile(POSITIVE_STRONG)),
    "pos_mild": (1, _compile(POSITIVE_MILD)),
}
_DENIAL = _compile(DENIAL)
_PROTECTIVE = _compile(PROTECTIVE)


@dataclass
class Sentiment:
    label: str                       # tiêu cực | tích cực | trung tính
    score: int
    reasons: List[str] = field(default_factory=list)   # matched keywords
    severity: int = 0                # 0 none, 2 strong, 3 critical (negative side only)
    denial: bool = False

    @property
    def is_crisis_grade(self) -> bool:
        """Strong/critical negative — the only tier that can page anyone."""
        return self.label == NEGATIVE and self.severity >= 2


def classify(title: str, extra_negative: List[str] = ()) -> Sentiment:
    text = title.lower()
    tiers = dict(_TIERS)
    if extra_negative:
        tiers["strong"] = (-2, tiers["strong"][1] + _compile([k.lower() for k in extra_negative]))

    denial = any(p.search(text) for _, p in _DENIAL)
    protective = any(p.search(text) for _, p in _PROTECTIVE)
    score, reasons, severity = 0, [], 0
    matched_spans: List[Tuple[int, int]] = []

    # longest keywords first so "nợ xấu tăng" wins over "nợ xấu"
    entries = sorted(
        ((weight, w, p) for weight, pats in tiers.values() for w, p in pats),
        key=lambda e: -len(e[1]),
    )
    for weight, word, pattern in entries:
        m = pattern.search(text)
        if not m:
            continue
        if any(m.start() < e and m.end() > s for s, e in matched_spans):
            continue   # already covered by a longer keyword
        matched_spans.append((m.start(), m.end()))
        if weight < 0 and (denial or (protective and weight > -3)):
            continue   # a denial / protective framing neutralises the bad-news words
        score += weight
        reasons.append(word)
        if weight < 0:
            severity = max(severity, -weight)

    if denial and score <= 0:
        return Sentiment(NEUTRAL, 0, ["phản hồi/bác bỏ"], 0, True)
    if score <= -1:
        return Sentiment(NEGATIVE, score, reasons, severity, denial)
    if score >= 1:
        return Sentiment(POSITIVE, score, reasons, 0, denial)
    return Sentiment(NEUTRAL, score, reasons, 0, denial)

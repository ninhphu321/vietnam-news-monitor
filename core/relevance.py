"""Economic-relevance filter: keep the feed about economy/finance/business
and drop clearly social/lifestyle/crime/sport stories that slip into
"economy" category feeds (user request, 2026-10: "chỉ những tin tức liên
quan kinh tế, hạn chế tin xã hội").

Rule-based, title-only (no AI, no article bodies — roadmap guardrails),
and deliberately CONSERVATIVE, because a false drop silently hides real
economic news while a false keep is just one extra line:

    drop  <=>  the title matches a SOCIAL term  AND  matches no ECON term

A title matching neither list is kept. ECON terms are intentionally broad
(sector words, money units, "dự án", "công ty"...), so a headline like
"Lại phập phồng thiếu điện" or "Gelex lên tiếng về việc thành viên HĐQT
bị khởi tố" survives even though it reads like crime/social news on the
surface. A real audit (2026-10-03, live crawl of 23 sources) showed a
plain "must contain an economic keyword" whitelist would have dropped
roughly a third of legitimate economy headlines, which is why this is a
blacklist-with-economic-override instead.

Both lists are hand-picked first cuts, tuned against that audit — same
"tune from real operation" status as HOT_KEYWORDS and the topic lists in
web/issues.py. Matching is on word boundaries over NFC-lowercased text
(core.normalization.normalize_for_matching), so short terms never fire
inside longer words.
"""

import re
from typing import Iterable, Optional

from core.normalization import normalize_for_matching

# Broad on purpose: anything that signals "this is about money, business,
# markets, industry or the economy" overrides a social match.
ECON_TERMS = (
    "kinh tế", "kinh doanh", "tài chính", "ngân hàng", "chứng khoán", "cổ phiếu", "cổ phần",
    "vn-index", "vnindex", "vn index", "hnx", "upcom", "trái phiếu", "tín dụng", "lãi suất", "tỷ giá", "tỉ giá",
    "ngoại tệ", "usd", "nhnn", "ngân sách", "thuế", "hải quan", "xuất khẩu", "nhập khẩu", "thương mại",
    "thị trường", "doanh nghiệp", "doanh thu", "lợi nhuận", "lãi", "lỗ", "tỷ đồng", "tỉ đồng", "triệu đồng",
    "tỷ usd", "tỉ usd", "đầu tư", "vốn", "bất động sản", "địa ốc", "nhà đất", "giá", "lạm phát", "gdp",
    "tăng trưởng", "vàng", "dầu", "xăng", "điện", "năng lượng", "than", "thép", "xi măng", "gạo", "cà phê",
    "cao su", "thủy sản", "nông sản", "bảo hiểm", "quỹ", "cổ tức", "cổ đông", "hđqt", "tập đoàn",
    "tổng công ty", "công ty", "niêm yết", "ipo", "sáp nhập", "m&a", "phát hành", "lương", "việc làm",
    "tiêu dùng", "bán lẻ", "sản xuất", "công nghiệp", "logistics", "hạ tầng", "dự án", "quy hoạch",
    "tiền", "nợ", "phá sản", "thương hiệu", "cung ứng", "chuỗi cung", "kim ngạch", "fed", "ecb", "opec",
    "lạm phát", "thất nghiệp", "an sinh", "bộ tài chính", "bộ công thương", "ngành", "khối ngoại", "tự doanh",
    "thanh khoản", "margin", "etf", "crypto", "tài sản mã hóa", "tiền số", "fintech", "startup", "khởi nghiệp",
    # added after the 2026-10-03 audit wrongly dropped e.g. "Con trai tỷ phú ... chi nghìn tỷ 'bắt đáy' HPG"
    # and "Thanh toán QR của du khách quốc tế ... tăng mạnh"
    "nghìn tỷ", "ngàn tỷ", "tỷ phú", "thanh toán", "thẻ", "qr", "tiết kiệm", "nông nghiệp", "nuôi trồng",
    "bitcoin", "tiền điện tử", "tiền ảo", "xuất siêu", "nhập siêu", "cpi", "pmi", "đổi mới sáng tạo", "giao dịch", "cổ phiếu", "bán hàng",
)

# Unambiguous non-economic topics only. When in doubt a term is left OUT
# (it would then need no ECON term to be dropped, so it must be safe).
SOCIAL_TERMS = (
    # weather / disaster
    "thời tiết", "mưa lớn", "mưa to", "mưa dông", "mưa lũ", "áp thấp", "nắng nóng", "rét đậm", "động đất", "sạt lở",
    "lũ quét", "không khí ngột", "bầu không khí",
    # crime / accident
    "tai nạn", "án mạng", "giết người", "cướp", "trộm", "ma túy", "bắt giữ", "hiếp dâm", "bạo hành", "đâm chết",
    # celebrity / lifestyle / family
    "showbiz", "ca sĩ", "diễn viên", "hoa hậu", "người mẫu", "ly hôn", "đám cưới", "hôn nhân",
    "chuyện tình", "mẹ chồng", "nàng dâu", "tâm linh", "phong thủy", "tử vi",
    "món ngon", "làm đẹp", "giảm cân",
    # sport / entertainment
    "bóng đá", "hlv", "cầu thủ", "v-league", "giải đấu", "sea games", "olympic", "world cup", "đội tuyển",
    "tennis", "thể thao", "điện ảnh", "ca khúc", "liveshow", "concert",
    # lottery
    "xổ số", "vietlott", "trúng số", "độc đắc", "giải nhất",
    # education / health
    "tuyển sinh", "thí sinh", "học sinh", "kỳ thi", "bệnh nhân",
    "dịch bệnh", "sốt xuất huyết", "ung thư", "đột quỵ",
    # pure software-release news (hardware launches are left alone: sales and
    # retail demand for them is economic news, e.g. "220.000 iPhone 18 đã được đặt mua")
    "ios",
    # politics-discipline / missing persons (found on a homepage feed, see crawlers/nguoiquansat.py)
    "khai trừ", "kỷ luật đảng", "mất tích", "tử vong", "thiệt mạng",
    # curiosities
    "tắm cho cá",
)


def _compile(terms: Iterable[str]) -> re.Pattern:
    # Longest first so multi-word terms win over a shorter prefix.
    ordered = sorted(set(terms), key=len, reverse=True)
    body = "|".join(re.escape(normalize_for_matching(t)) for t in ordered)
    return re.compile(rf"(?<!\w)(?:{body})(?!\w)")


_ECON = _compile(ECON_TERMS)
_SOCIAL = _compile(SOCIAL_TERMS)


def matched_terms(title: str) -> tuple:
    """(econ_hit, social_hit) — the first term of each list found in the
    title (None if none). Exposed so dry-runs/audits can say *why*."""
    text = normalize_for_matching(title)
    e, s = _ECON.search(text), _SOCIAL.search(text)
    return (e.group(0) if e else None, s.group(0) if s else None)


def is_economic(title: str) -> bool:
    """False only for a clearly social title with no economic signal."""
    econ, social = matched_terms(title)
    return not (social and not econ)


def drop_reason(title: str) -> Optional[str]:
    """The social term that got this title dropped, or None if kept."""
    econ, social = matched_terms(title)
    return social if (social and not econ) else None

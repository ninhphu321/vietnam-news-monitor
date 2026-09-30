"""Signal lifecycle classification (roadmap V2 §15).

    EMERGING -> ACCELERATING -> PEAK -> COOLING

Deliberately does NOT add a literal "ARCHIVED" status stored anywhere:
an issue that stops appearing in today's Top Issues simply has no row
for today at all, which tests/test_datainfra.py's `issue_streaks()`
(current_streak == 0) already surfaces as "not hot today" — adding a
fifth persisted state for the same fact the data already encodes would
be exactly the kind of unneeded complexity the roadmap's own rule 2
("không rewrite architecture hiện tại chỉ vì thấy architecture khác
đẹp hơn") warns against.

Purely a function of two numbers plus "is this the issue's first
appearance today" — no database access here, so it's trivially unit
testable and callers (scheduler.snapshot_data) own all the I/O.
"""

from typing import Optional

EMERGING = "emerging"
ACCELERATING = "accelerating"
PEAK = "peak"
COOLING = "cooling"

# How much faster/slower than last cycle counts as a real direction
# change rather than noise. +-15% chosen as a first cut — not derived
# from labeled data (see TONG-QUAN-DU-AN.md's honesty note on keyword/
# rule engines needing tuning from real operation, same idea applies
# to any hand-picked threshold).
ACCELERATION_UP = 1.15
ACCELERATION_DOWN = 0.85

# Single source of truth for how each status is shown to a human,
# reused by both the website (web/generate_site.py, which adds its own
# CSS class alongside this text) and Telegram (telegram.py's "TOP
# SIGNALS" section, roadmap V2 §19) so the two surfaces can never
# drift into describing the same status with different words.
LIFECYCLE_LABELS = {
    EMERGING: "★ Mới xuất hiện",
    ACCELERATING: "↑ Đang tăng tốc",
    PEAK: "● Ổn định",
    COOLING: "↓ Đang hạ nhiệt",
}


def classify_lifecycle(velocity_now: float, velocity_previous: Optional[float]) -> str:
    """`velocity_previous` is None when the issue has no row yet today
    (its first cycle appearing) -> always EMERGING, regardless of its
    velocity value, since there is nothing yet to compare against."""
    if velocity_previous is None:
        return EMERGING
    if velocity_previous <= 0:
        return ACCELERATING if velocity_now > 0 else PEAK
    ratio = velocity_now / velocity_previous
    if ratio >= ACCELERATION_UP:
        return ACCELERATING
    if ratio <= ACCELERATION_DOWN:
        return COOLING
    return PEAK


# Roadmap V3 §26 "Signal Alert": only page Telegram when a signal clears
# ALL three bars at once (source diversity AND score), to keep a
# dedicated alert rare and worth interrupting for — the regular "TOP
# TÍN HIỆU" digest section already lists the Top 5 every cycle
# regardless of any threshold, so this is strictly a *smaller*, higher-
# bar subset of that, not a duplicate. Chosen intuitively, same "tune
# from real data" spirit as ACCELERATION_UP/DOWN above and every other
# hand-picked threshold in this project:
#   - min_sources=3 matches CRISIS_MIN_SOURCES's own bar for "several
#     independent outlets", not arbitrary.
#   - min_score=70 puts it in the top tier of that cycle's own Top 5
#     (hot_score is normalized 0-100 *relative to the day's strongest
#     issue*, so this is "clearly a leader that cycle", not an absolute
#     universal cutoff).
ALERT_MIN_SOURCES = 3
ALERT_MIN_SCORE = 70.0


def should_alert(source_count: int, hot_score: float, min_sources: int = ALERT_MIN_SOURCES,
                  min_score: float = ALERT_MIN_SCORE) -> bool:
    """Whether an issue that just transitioned to ACCELERATING (the
    caller, scheduler.snapshot_data, is responsible for only calling
    this on a real transition — see its docstring for why that's what
    keeps this from spamming Telegram every cycle) is alert-worthy."""
    return source_count >= min_sources and hot_score >= min_score

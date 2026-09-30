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

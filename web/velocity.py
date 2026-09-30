"""Velocity Engine (roadmap V3 §22-23): a fixed-window read on how fast
an issue is accumulating articles *right now*, separate from the
whole-lifetime-average velocity/acceleration `web/issues.py` already
computes for SignalScore's ranking formula (a quarter-of-the-issue's-
own-lifespan split — good for ranking, not for "is this issue moving
right now" in absolute terms comparable across issues of different
ages).

The roadmap's §22 lists 7 window sizes (5min...24h) to illustrate *why*
raw article counts miss acceleration, not a requirement to render 7
numbers at once — nothing in the roadmap's own wireframes (§18, §55)
shows more than one rate. `calculate_velocity()` takes one configurable
`window` (default 1h, the same order of magnitude as
`web.signals.classify_lifecycle`'s own cross-cycle comparison and
`CRISIS_WINDOW_MINUTES`) and compares it against the window right
before it.

Reuses web.signals' EMERGING/ACCELERATING/PEAK/COOLING vocabulary and
ACCELERATION_UP/DOWN thresholds instead of inventing a second,
competing status system — the underlying comparison differs (a fixed
trailing window recomputed fresh every build vs. a cross-cycle
comparison persisted in issue_history), but a reader shouldn't have to
learn two different words for "speeding up".
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List

from web.signals import ACCELERATING, ACCELERATION_DOWN, ACCELERATION_UP, COOLING, EMERGING, PEAK

DEFAULT_WINDOW = timedelta(hours=1)


@dataclass
class VelocityResult:
    current_rate: float  # articles/hour in the most recent `window`
    previous_rate: float  # articles/hour in the window immediately before
    acceleration: float  # current_rate / previous_rate (see calculate_velocity for the zero-previous case)
    status: str  # one of web.signals.{EMERGING,ACCELERATING,PEAK,COOLING}


def calculate_velocity(
    timestamps: List[datetime],
    now: datetime,
    window: timedelta = DEFAULT_WINDOW,
) -> VelocityResult:
    """`timestamps` is an issue's article timestamps, any order. Splits
    the trailing `2 * window` ending at `now` into two adjacent
    buckets: `(now - window, now]` is "current", `(now - 2*window,
    now - window]` is "previous".

    Edge cases (no ratio is computable when the previous bucket is
    empty):
    - both buckets empty -> COOLING (issue has gone quiet in this window)
    - only the current bucket has articles -> EMERGING (a fresh burst
      where there was nothing right before it)
    - both non-empty -> ratio-classified exactly like classify_lifecycle
    """
    if now.tzinfo is None:
        raise ValueError("calculate_velocity() requires a timezone-aware `now`")

    window_hours = window.total_seconds() / 3600
    current_start = now - window
    previous_start = now - 2 * window

    current_count = sum(1 for t in timestamps if current_start < t <= now)
    previous_count = sum(1 for t in timestamps if previous_start < t <= current_start)

    current_rate = current_count / window_hours
    previous_rate = previous_count / window_hours

    if previous_count == 0:
        if current_count == 0:
            status = COOLING
            acceleration = 0.0
        else:
            status = EMERGING
            acceleration = float(current_count)
    else:
        acceleration = current_rate / previous_rate
        if acceleration >= ACCELERATION_UP:
            status = ACCELERATING
        elif acceleration <= ACCELERATION_DOWN:
            status = COOLING
        else:
            status = PEAK

    return VelocityResult(
        current_rate=round(current_rate, 2),
        previous_rate=round(previous_rate, 2),
        acceleration=round(acceleration, 2),
        status=status,
    )

"""Email warm-up scheduler — a new/unproven SMTP account is far more likely
to get throttled or flagged if it jumps straight to a high daily volume with
no sending history, so the daily send cap ramps up gradually over the first
two weeks instead of applying the user's full configured limit from day one.

This is a deliberately conservative, generic ramp — not tuned to any specific
mailbox provider — since there is no live SMTP account or real send history
available to calibrate against real-world deliverability in this environment.
What's verified here is the mechanism (day math, correct caps enforced) not
real-world outcomes; see CLAUDE.md's checkpoint for this item for the explicit
scope of what could and couldn't be verified.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

# (inclusive day-index upper bound, cap for that phase). Day 0 is the first
# calendar day any email was ever sent. After the last bound, the ramp is
# considered complete and the user's own configured daily limit applies.
RAMP_SCHEDULE = [
    (2, 20),    # days 0-2:  20/day
    (4, 50),    # days 3-4:  50/day
    (7, 100),   # days 5-7:  100/day
    (10, 150),  # days 8-10: 150/day
    (13, 200),  # days 11-13: 200/day
]

RAMP_DURATION_DAYS = 14
DATE_FORMAT = "%Y-%m-%d"


def days_since_start(start_date: date, today: date) -> int:
    """Non-negative day index — 0 on the first day, never negative even if
    `today` is somehow before `start_date` (e.g. a clock change)."""
    return max((today - start_date).days, 0)


def is_warmup_active(start_date: date, today: date) -> bool:
    return days_since_start(start_date, today) < RAMP_DURATION_DAYS


def warmup_cap_for_day(day_index: int, target_daily_limit: int) -> int:
    """The ramp never recommends sending MORE than the user's own configured
    daily limit — it only ever narrows it during the ramp window."""
    day_index = max(day_index, 0)
    for max_day, cap in RAMP_SCHEDULE:
        if day_index <= max_day:
            return min(cap, target_daily_limit)
    return target_daily_limit


def effective_daily_cap(start_date: Optional[date], today: date, target_daily_limit: int) -> int:
    """The real cap to enforce today: the user's configured daily limit,
    narrowed by the warm-up ramp if a warm-up start date is set and the
    ramp window hasn't finished yet. No start date recorded yet (a brand
    new install that has never sent) is treated as "not started" — the
    caller is expected to set the start date on the first real send."""
    if start_date is None or not is_warmup_active(start_date, today):
        return target_daily_limit
    return warmup_cap_for_day(days_since_start(start_date, today), target_daily_limit)


def parse_date(value: str) -> Optional[date]:
    if not value:
        return None
    try:
        return datetime.strptime(value, DATE_FORMAT).date()
    except (ValueError, TypeError):
        return None


def format_date(d: date) -> str:
    return d.strftime(DATE_FORMAT)


def ramp_status_text(start_date: Optional[date], today: date, target_daily_limit: int) -> str:
    """Human-readable summary for the Settings UI."""
    if start_date is None:
        return f"Warm-up not started yet — first send will begin a {RAMP_DURATION_DAYS}-day ramp."
    day_index = days_since_start(start_date, today)
    if not is_warmup_active(start_date, today):
        return f"Warm-up complete (started {format_date(start_date)}) — full daily limit applies."
    cap = warmup_cap_for_day(day_index, target_daily_limit)
    return (f"Warm-up day {day_index + 1} of {RAMP_DURATION_DAYS} "
            f"(started {format_date(start_date)}) — today's cap: {cap}/day.")

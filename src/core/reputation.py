"""Reputation / "recommended safe volume today" indicator (Item 6, final
completion pass) -- a basic, honest signal combining the email warm-up
ramp (core/warmup_scheduler.py) with any real, recently-logged failure
rate, so a user sees a single, conservative recommendation rather than
having to reconcile the raw daily-limit slider against warm-up status
themselves.

No sample/fabricated data is ever used here -- with zero real send
history, the failure-rate signal is "unknown" and the recommendation is
simply the warm-up ramp's own conservative day-0 default. This can only
ever narrow the warm-up cap further (in response to a real, elevated
failure rate), never widen it beyond what warm-up itself already allows.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from . import warmup_scheduler

# Recent-failure-rate thresholds. Deliberately conservative and generic --
# not tuned against any real ESP's actual blocklist behavior, since no live
# SMTP account/send history is available in this environment to calibrate
# against (see this item's CLAUDE.md checkpoint for the explicit scope
# limitation).
HIGH_RISK_FAILURE_RATE = 0.10
MEDIUM_RISK_FAILURE_RATE = 0.03

RECENT_WINDOW_DAYS = 7


@dataclass
class FailureSignal:
    sent: int
    failed: int

    @property
    def total(self) -> int:
        return self.sent + self.failed

    @property
    def failure_rate(self) -> Optional[float]:
        """None means "no real signal yet" -- not zero risk, just unknown."""
        if self.total == 0:
            return None
        return self.failed / self.total

    @property
    def risk_level(self) -> str:
        """"unknown" (no real data), "low", "medium", or "high"."""
        rate = self.failure_rate
        if rate is None:
            return "unknown"
        if rate > HIGH_RISK_FAILURE_RATE:
            return "high"
        if rate > MEDIUM_RISK_FAILURE_RATE:
            return "medium"
        return "low"


@dataclass
class SafeVolumeRecommendation:
    recommended: int
    warmup_cap: int
    risk_level: str
    failure_rate: Optional[float]
    reason: str


def compute_failure_signal(stats: dict) -> FailureSignal:
    return FailureSignal(sent=int(stats.get("sent", 0)), failed=int(stats.get("failed", 0)))


def recommended_safe_volume_today(
    start_date: Optional[date], today: date, target_daily_limit: int,
    signal: FailureSignal,
) -> SafeVolumeRecommendation:
    """The warm-up ramp's own cap is the ceiling -- a real, elevated recent
    failure rate can only narrow it further, never widen it."""
    warmup_cap = warmup_scheduler.effective_daily_cap(start_date, today, target_daily_limit)
    risk = signal.risk_level

    if risk == "high":
        recommended = max(int(warmup_cap * 0.25), 5)
        reason = (f"Recent failure rate is {signal.failure_rate:.0%} over the last "
                   f"{RECENT_WINDOW_DAYS} days — well above a healthy range. Recommending a "
                   f"much lower volume than your warm-up cap until this improves.")
    elif risk == "medium":
        recommended = max(int(warmup_cap * 0.5), 10)
        reason = (f"Recent failure rate is {signal.failure_rate:.0%} over the last "
                   f"{RECENT_WINDOW_DAYS} days — somewhat elevated. Recommending half your "
                   f"warm-up cap as a precaution.")
    elif risk == "low":
        recommended = warmup_cap
        reason = (f"Recent failure rate is {signal.failure_rate:.0%} over the last "
                   f"{RECENT_WINDOW_DAYS} days — healthy. Following the warm-up ramp's own cap.")
    else:
        recommended = warmup_cap
        reason = ("No recent send history yet — starting with the warm-up ramp's conservative "
                   "default until there's real data to base a recommendation on.")

    return SafeVolumeRecommendation(
        recommended=recommended, warmup_cap=warmup_cap, risk_level=risk,
        failure_rate=signal.failure_rate, reason=reason,
    )

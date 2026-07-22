"""Pure-logic tests for the reputation / safe-volume indicator (Item 6,
final completion pass). No real send history exists in this environment,
so these tests only verify the mechanism -- correct risk-level
classification, correct capping (never above the warm-up ramp's own cap),
and correct "unknown" handling with zero fabricated data -- not real-world
deliverability outcomes."""

from datetime import date

from src.core import reputation as R


def test_failure_signal_unknown_with_no_data():
    signal = R.compute_failure_signal({"sent": 0, "failed": 0})
    assert signal.total == 0
    assert signal.failure_rate is None
    assert signal.risk_level == "unknown"


def test_failure_signal_risk_levels():
    low = R.compute_failure_signal({"sent": 100, "failed": 1})
    assert low.risk_level == "low"

    medium = R.compute_failure_signal({"sent": 95, "failed": 5})
    assert medium.risk_level == "medium"

    high = R.compute_failure_signal({"sent": 80, "failed": 20})
    assert high.risk_level == "high"


def test_failure_signal_rate_computed_correctly():
    signal = R.compute_failure_signal({"sent": 90, "failed": 10})
    assert signal.failure_rate == 0.10


def test_recommendation_with_no_warmup_start_follows_full_limit():
    # No warm-up start date recorded yet (a brand new install that has
    # never sent) -- effective_daily_cap treats this as "warm-up not
    # started", not "day 0", so the full configured limit applies until
    # the first real send records a start date.
    signal = R.compute_failure_signal({"sent": 0, "failed": 0})
    rec = R.recommended_safe_volume_today(None, date(2026, 1, 1), 300, signal)
    assert rec.risk_level == "unknown"
    assert rec.recommended == rec.warmup_cap == 300


def test_recommendation_with_no_failure_history_matches_warmup_day_zero_cap():
    signal = R.compute_failure_signal({"sent": 0, "failed": 0})
    start = date(2026, 1, 1)
    rec = R.recommended_safe_volume_today(start, start, 300, signal)
    assert rec.risk_level == "unknown"
    assert rec.recommended == rec.warmup_cap == 20  # day-0 warm-up default
    assert "no recent send history" in rec.reason.lower() or "no real" in rec.reason.lower()


def test_recommendation_never_exceeds_warmup_cap_even_at_low_risk():
    signal = R.compute_failure_signal({"sent": 1000, "failed": 1})
    start = date(2026, 1, 1)
    rec = R.recommended_safe_volume_today(start, start, 300, signal)
    assert rec.recommended == rec.warmup_cap  # low risk follows the cap, never exceeds it


def test_recommendation_narrows_cap_on_medium_risk():
    signal = R.compute_failure_signal({"sent": 95, "failed": 5})
    start = date(2026, 1, 1)
    # Past warm-up (day 20), so warmup_cap == full target limit (300).
    rec = R.recommended_safe_volume_today(start, date(2026, 1, 21), 300, signal)
    assert rec.warmup_cap == 300
    assert rec.recommended == 150  # half the cap
    assert rec.recommended < rec.warmup_cap


def test_recommendation_narrows_cap_sharply_on_high_risk():
    signal = R.compute_failure_signal({"sent": 70, "failed": 30})
    start = date(2026, 1, 1)
    rec = R.recommended_safe_volume_today(start, date(2026, 1, 21), 300, signal)
    assert rec.recommended == 75  # 25% of the cap
    assert rec.recommended < rec.warmup_cap


def test_recommendation_has_a_floor_even_at_high_risk_with_a_tiny_cap():
    signal = R.compute_failure_signal({"sent": 70, "failed": 30})
    start = date(2026, 1, 1)
    rec = R.recommended_safe_volume_today(start, start, 10, signal)  # day-0 cap = min(20, 10) = 10
    assert rec.recommended >= 5  # floor, never recommends an unusably tiny number

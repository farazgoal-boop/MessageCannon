"""Pure-logic tests for the email warm-up scheduler (Item 3 of the final
completion pass). No SMTP account or real send history exists in this
environment, so what's verified here is the mechanism -- correct day math,
correct caps at every ramp boundary, never recommending above the user's own
configured limit -- not real-world deliverability outcomes."""

from datetime import date, timedelta

from src.core import warmup_scheduler as W


def test_days_since_start_never_negative():
    today = date(2026, 1, 10)
    assert W.days_since_start(today, today) == 0
    assert W.days_since_start(today - timedelta(days=5), today) == 5
    # Clock skew / future start date shouldn't produce a negative index.
    assert W.days_since_start(today + timedelta(days=3), today) == 0


def test_warmup_cap_follows_ramp_schedule_boundaries():
    target = 500
    assert W.warmup_cap_for_day(0, target) == 20
    assert W.warmup_cap_for_day(2, target) == 20
    assert W.warmup_cap_for_day(3, target) == 50
    assert W.warmup_cap_for_day(4, target) == 50
    assert W.warmup_cap_for_day(5, target) == 100
    assert W.warmup_cap_for_day(7, target) == 100
    assert W.warmup_cap_for_day(8, target) == 150
    assert W.warmup_cap_for_day(10, target) == 150
    assert W.warmup_cap_for_day(11, target) == 200
    assert W.warmup_cap_for_day(13, target) == 200
    assert W.warmup_cap_for_day(14, target) == target
    assert W.warmup_cap_for_day(100, target) == target


def test_warmup_cap_never_exceeds_users_own_target_even_mid_ramp():
    # A user with a low configured daily limit (e.g. 10) should never be
    # ramped UP to a higher number than they themselves configured.
    assert W.warmup_cap_for_day(0, 10) == 10
    assert W.warmup_cap_for_day(5, 10) == 10
    assert W.warmup_cap_for_day(11, 10) == 10


def test_is_warmup_active_true_during_ramp_false_after():
    start = date(2026, 1, 1)
    assert W.is_warmup_active(start, start) is True
    assert W.is_warmup_active(start, start + timedelta(days=13)) is True
    assert W.is_warmup_active(start, start + timedelta(days=14)) is False
    assert W.is_warmup_active(start, start + timedelta(days=30)) is False


def test_effective_daily_cap_no_start_date_means_full_limit():
    # A brand new install with no warm-up start date recorded yet isn't
    # ramped -- the caller is expected to set the start date on first send.
    assert W.effective_daily_cap(None, date(2026, 1, 1), 300) == 300


def test_effective_daily_cap_ramps_then_releases_to_full_limit():
    start = date(2026, 1, 1)
    assert W.effective_daily_cap(start, start, 300) == 20
    assert W.effective_daily_cap(start, start + timedelta(days=6), 300) == 100
    assert W.effective_daily_cap(start, start + timedelta(days=14), 300) == 300
    assert W.effective_daily_cap(start, start + timedelta(days=100), 300) == 300


def test_parse_and_format_date_round_trip():
    d = date(2026, 3, 5)
    text = W.format_date(d)
    assert text == "2026-03-05"
    assert W.parse_date(text) == d
    assert W.parse_date("") is None
    assert W.parse_date("not-a-date") is None


def test_ramp_status_text_reflects_state():
    assert "not started" in W.ramp_status_text(None, date(2026, 1, 1), 300)

    start = date(2026, 1, 1)
    mid_text = W.ramp_status_text(start, start + timedelta(days=5), 300)
    assert "day 6 of 14" in mid_text
    assert "100/day" in mid_text

    done_text = W.ramp_status_text(start, start + timedelta(days=20), 300)
    assert "complete" in done_text

"""Reputation / "recommended safe volume today" indicator (Item 6, final
completion pass) -- _update_reputation_indicator on MainWindow. Uses a
dedicated, module-scoped, fresh-DB MainWindow (same pattern as
test_email_warmup_enforcement.py) so real message_logs rows can be
inserted without ever touching the live production database.
"""

import tkinter as tk
from datetime import date, datetime, time

import pytest

from src.core import warmup_scheduler
from src.models import MessageLog, MessageStatus


def _close_any_toplevel(window) -> None:
    def walk(widget):
        for child in widget.children.values():
            if isinstance(child, tk.Toplevel):
                return child
            found = walk(child)
            if found:
                return found
        return None
    top = walk(window)
    if top is not None:
        top.destroy()


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    from src.database import db_manager as db_manager_module

    mp = pytest.MonkeyPatch()
    fresh_db_path = str(tmp_path_factory.mktemp("reputation") / "test.db")
    mp.setattr(db_manager_module, "get_database_path", lambda: fresh_db_path)
    db_manager_module.DatabaseManager._instance = None

    from src.ui.main_window import MainWindow

    win = MainWindow()
    _close_any_toplevel(win)
    win.update()
    try:
        yield win
    finally:
        try:
            if win.winfo_exists():
                win.destroy()
        except Exception:
            pass
        db_manager_module.DatabaseManager._instance = None
        mp.undo()


@pytest.fixture(autouse=True)
def _reset_state(window):
    window._email_warmup_start_date = ""
    window.daily_limit_var.set(300)
    with window.db.get_connection() as conn:
        conn.execute("DELETE FROM message_logs")
        conn.commit()
    yield
    window._email_warmup_start_date = ""
    with window.db.get_connection() as conn:
        conn.execute("DELETE FROM message_logs")
        conn.commit()


def test_indicator_shows_full_limit_with_no_warmup_start_recorded(window):
    # No warm-up start date at all (a brand new install that has never
    # sent) means warm-up hasn't begun -- effective_daily_cap treats this
    # as "not started", not "day 0", so the full configured daily limit
    # applies until the first real send records a start date.
    window._update_reputation_indicator()
    text = window.reputation_label.cget("text")
    assert "Recommended safe volume today" in text
    assert "300/day" in text
    assert "No recent send history" in text


def test_indicator_reflects_day_zero_warmup_cap(window):
    window._email_warmup_start_date = warmup_scheduler.format_date(date.today())
    window._update_reputation_indicator()
    text = window.reputation_label.cget("text")
    assert "20/day" in text


def test_indicator_narrows_on_real_logged_failures(window):
    from src.ui import theme as T

    window._email_warmup_start_date = warmup_scheduler.format_date(date.today())
    # Push warm-up fully past its ramp so the base cap is the full 300,
    # making the failure-driven narrowing unambiguous in the assertion.
    window._email_warmup_start_date = warmup_scheduler.format_date(
        date.today() - __import__("datetime").timedelta(days=20))

    for i in range(7):
        window.db.add_message_log(MessageLog(
            contact_email=f"s{i}@test.dev", message_text="hi", status=MessageStatus.SENT,
            sent_at=datetime.combine(date.today(), time(9, 0))))
    for i in range(3):
        window.db.add_message_log(MessageLog(
            contact_email=f"f{i}@test.dev", message_text="hi", status=MessageStatus.FAILED))

    window._update_reputation_indicator()
    text = window.reputation_label.cget("text")
    assert "75/day" in text  # 30% failure rate -> high risk -> 25% of the 300 cap
    assert window.reputation_label.cget("text_color") == T.DANGER_ON_BADGE


def test_indicator_shows_medium_risk_narrowing_at_a_moderate_failure_rate(window):
    window._email_warmup_start_date = warmup_scheduler.format_date(
        date.today() - __import__("datetime").timedelta(days=20))

    for i in range(95):
        window.db.add_message_log(MessageLog(
            contact_email=f"s{i}@test.dev", message_text="hi", status=MessageStatus.SENT,
            sent_at=datetime.combine(date.today(), time(9, 0))))
    for i in range(5):
        window.db.add_message_log(MessageLog(
            contact_email=f"f{i}@test.dev", message_text="hi", status=MessageStatus.FAILED))

    window._update_reputation_indicator()
    text = window.reputation_label.cget("text")
    assert "150/day" in text  # 5% failure rate -> medium risk -> half the 300 cap


def test_indicator_refreshes_alongside_warmup_status_label(window):
    """_update_email_warmup_status_label is the single call site every
    other part of the app already uses to refresh warm-up state (settings
    load, toggle, daily-limit slider change) -- confirms the reputation
    indicator piggybacks on that same call rather than needing its own
    separate wiring at every site."""
    window._email_warmup_start_date = ""
    window._update_email_warmup_status_label()
    before = window.reputation_label.cget("text")

    window._email_warmup_start_date = warmup_scheduler.format_date(date.today())
    window._update_email_warmup_status_label()
    after = window.reputation_label.cget("text")

    assert before != after

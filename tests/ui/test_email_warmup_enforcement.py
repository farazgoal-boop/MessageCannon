"""Email warm-up scheduler enforcement (Item 3, final completion pass) --
_start_email_from_compose must block a send that would exceed today's
warm-up-ramped cap, and _ensure_email_warmup_started must record day 0 on
the first real successful send. Uses a dedicated, module-scoped, fresh-DB
MainWindow (same pattern as test_contact_delete.py) so a real "successful
send" doesn't require real SMTP -- the settings/DB bookkeeping is what's
under test, not delivery itself.
"""

import tkinter as tk
from datetime import date, datetime, time
from tkinter import messagebox

import pytest

from src.core import warmup_scheduler
from src.models import Contact, MessageLog, MessageStatus


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
    fresh_db_path = str(tmp_path_factory.mktemp("email_warmup") / "test.db")
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
def _reset_warmup_state(window):
    """Every test in this file gets a clean warm-up state and a clean
    message_logs table, since these tests share one module-scoped window."""
    window._email_warmup_start_date = ""
    window.email_warmup_enabled_var.set(True)
    window.daily_limit_var.set(50)
    with window.db.get_connection() as conn:
        conn.execute("DELETE FROM message_logs")
        conn.commit()
    yield
    window._email_warmup_start_date = ""
    with window.db.get_connection() as conn:
        conn.execute("DELETE FROM message_logs")
        conn.commit()


def test_remaining_today_full_cap_when_not_started(window):
    window.daily_limit_var.set(300)
    assert window._email_warmup_remaining_today() == 300


def test_remaining_today_ramped_cap_on_day_zero(window):
    window._email_warmup_start_date = warmup_scheduler.format_date(date.today())
    window.daily_limit_var.set(300)
    assert window._email_warmup_remaining_today() == 20  # day-0 ramp cap


def test_remaining_today_subtracts_already_sent(window):
    window._email_warmup_start_date = warmup_scheduler.format_date(date.today())
    window.daily_limit_var.set(300)
    window.db.add_message_log(MessageLog(
        contact_email="a@test.dev", message_text="hi", status=MessageStatus.SENT,
        sent_at=datetime.combine(date.today(), time(9, 0))))
    window.db.add_message_log(MessageLog(
        contact_email="b@test.dev", message_text="hi", status=MessageStatus.SENT,
        sent_at=datetime.combine(date.today(), time(10, 0))))
    assert window._email_warmup_remaining_today() == 18  # 20 - 2 already sent


def test_ensure_warmup_started_sets_once_and_does_not_overwrite(window):
    assert window._email_warmup_start_date == ""
    window._ensure_email_warmup_started()
    first = window._email_warmup_start_date
    assert first == warmup_scheduler.format_date(date.today())

    window._email_warmup_start_date = "2020-01-01"  # simulate an existing earlier start
    window._ensure_email_warmup_started()
    assert window._email_warmup_start_date == "2020-01-01", (
        "must never overwrite an already-recorded warm-up start date")


def test_start_email_from_compose_blocks_when_recipients_exceed_warmup_cap(window, monkeypatch):
    window._email_warmup_start_date = warmup_scheduler.format_date(date.today())
    window.daily_limit_var.set(300)  # day-0 ramp cap will be 20 regardless

    original_contacts = window.contacts
    original_thread = window._em_send_thread
    try:
        # 21 contacts with email > the day-0 cap of 20.
        window.contacts = [
            Contact(id=i, name=f"C{i}", phone=f"+1000000{i:04d}", email=f"c{i}@test.dev")
            for i in range(21)
        ]
        window._em_user.set("sender@test.dev")
        window._em_pass.set("app-password")
        window._em_subj_var.set("Hello {name}!")
        window._compose_em_body.delete("1.0", "end")
        window._compose_em_body.insert("1.0", "<p>Hi {name}</p>")

        warned = {}

        def fake_showwarning(title, message):
            warned["title"] = title
            warned["message"] = message

        monkeypatch.setattr(messagebox, "showwarning", fake_showwarning)

        window._start_email_from_compose()
        window.update()

        assert warned.get("title") == "Warm-Up Limit"
        assert "20" in warned.get("message", "")
        assert window._em_send_thread is original_thread, (
            "a warm-up-blocked send must never start the send thread")
    finally:
        window.contacts = original_contacts
        window._em_send_thread = original_thread


def test_start_email_from_compose_allowed_when_warmup_disabled(window, monkeypatch):
    window._email_warmup_start_date = warmup_scheduler.format_date(date.today())
    window.daily_limit_var.set(300)
    window.email_warmup_enabled_var.set(False)  # explicit opt-out

    original_contacts = window.contacts
    try:
        window.contacts = [
            Contact(id=i, name=f"C{i}", phone=f"+1000001{i:04d}", email=f"d{i}@test.dev")
            for i in range(21)
        ]
        # Intentionally leave SMTP unconfigured so this fails at the *next*
        # gate (SMTP not configured) rather than actually sending real email
        # -- proves the warm-up gate specifically was skipped, without this
        # test needing a real/mocked SMTP server.
        window._em_user.set("")
        window._em_pass.set("")

        warned = {}
        monkeypatch.setattr(messagebox, "showwarning", lambda t, m: warned.update(title=t, message=m))

        window._start_email_from_compose()
        window.update()

        assert "title" not in warned, "warm-up gate must not fire when the toggle is off"
        assert "SMTP not configured" in window.progress_status_var.get()
    finally:
        window.contacts = original_contacts

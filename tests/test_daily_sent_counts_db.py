"""Item 37 (UI/UX benchmark pass vs premium tools): DB-level coverage for
get_daily_sent_counts, the real data source behind the new Campaigns
dashboard sparkline. Uses a throwaway temp-file SQLite database, never the
real user database."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from src.database.db_manager import DatabaseManager
from src.models import MessageLog, MessageStatus


def _make_db(tmp_path):
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = str(tmp_path / "sparkline_test.db")
    db._initialize_database()
    return db


def test_returns_seven_days_oldest_first_today_last(tmp_path):
    db = _make_db(tmp_path)
    counts = db.get_daily_sent_counts(days=7)
    assert len(counts) == 7
    assert all(isinstance(c, int) for c in counts)


def test_counts_real_email_sends_on_the_right_day(tmp_path):
    db = _make_db(tmp_path)
    today = date.today()
    for i in range(3):
        db.add_message_log(MessageLog(
            contact_email=f"s{i}@test.dev", message_text="hi", status=MessageStatus.SENT,
            sent_at=datetime.combine(today, time(9, 0))))
    counts = db.get_daily_sent_counts(days=7)
    assert counts[-1] == 3  # today is the last entry
    assert sum(counts[:-1]) == 0


def test_counts_real_whatsapp_sends_on_the_right_day(tmp_path):
    db = _make_db(tmp_path)
    today = date.today()
    for i in range(2):
        db.create_tracked_message(
            phone=f"+9231600000{i}", message_text="hi", status="delivered",
            sent_at=datetime.combine(today, time(10, 0)))
    counts = db.get_daily_sent_counts(days=7)
    assert counts[-1] == 2


def test_combines_both_channels_on_the_same_day(tmp_path):
    db = _make_db(tmp_path)
    today = date.today()
    db.add_message_log(MessageLog(
        contact_email="a@test.dev", message_text="hi", status=MessageStatus.SENT,
        sent_at=datetime.combine(today, time(9, 0))))
    db.create_tracked_message(
        phone="+923160000000", message_text="hi", status="read",
        sent_at=datetime.combine(today, time(10, 0)))
    counts = db.get_daily_sent_counts(days=7)
    assert counts[-1] == 2


def test_excludes_rows_older_than_the_window(tmp_path):
    db = _make_db(tmp_path)
    old = date.today() - timedelta(days=30)
    db.add_message_log(MessageLog(
        contact_email="old@test.dev", message_text="hi", status=MessageStatus.SENT,
        sent_at=datetime.combine(old, time(9, 0))))
    counts = db.get_daily_sent_counts(days=7)
    assert sum(counts) == 0


def test_failed_and_pending_messages_are_not_counted(tmp_path):
    db = _make_db(tmp_path)
    today = date.today()
    db.add_message_log(MessageLog(
        contact_email="failed@test.dev", message_text="hi", status=MessageStatus.FAILED))
    db.create_tracked_message(
        phone="+923160000001", message_text="hi", status="pending")
    counts = db.get_daily_sent_counts(days=7)
    assert sum(counts) == 0

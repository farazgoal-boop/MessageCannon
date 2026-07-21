"""DB-level coverage for get_email_sent_count_on (Item 3, final completion
pass) -- the cumulative "how many emails already went out today" count the
warm-up scheduler's enforcement check relies on. Uses a throwaway temp-file
SQLite database, never the real user database."""

from datetime import date, datetime, time, timedelta

from src.database.db_manager import DatabaseManager
from src.models import MessageLog, MessageStatus


def _make_db(tmp_path):
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = str(tmp_path / "warmup_test.db")
    db._initialize_database()
    return db


def test_counts_only_sent_status_for_the_given_day(tmp_path):
    db = _make_db(tmp_path)
    today = date.today()
    yesterday = today - timedelta(days=1)

    db.add_message_log(MessageLog(
        contact_email="a@test.dev", message_text="hi", status=MessageStatus.SENT,
        sent_at=datetime.combine(today, time(9, 0))))
    db.add_message_log(MessageLog(
        contact_email="b@test.dev", message_text="hi", status=MessageStatus.SENT,
        sent_at=datetime.combine(today, time(14, 30))))
    # A failed send today shouldn't count toward the sent total.
    db.add_message_log(MessageLog(
        contact_email="c@test.dev", message_text="hi", status=MessageStatus.FAILED,
        sent_at=datetime.combine(today, time(10, 0))))
    # A sent message from yesterday shouldn't count toward today's total.
    db.add_message_log(MessageLog(
        contact_email="d@test.dev", message_text="hi", status=MessageStatus.SENT,
        sent_at=datetime.combine(yesterday, time(9, 0))))

    assert db.get_email_sent_count_on(today.strftime("%Y-%m-%d")) == 2
    assert db.get_email_sent_count_on(yesterday.strftime("%Y-%m-%d")) == 1


def test_returns_zero_when_nothing_sent(tmp_path):
    db = _make_db(tmp_path)
    assert db.get_email_sent_count_on(date.today().strftime("%Y-%m-%d")) == 0

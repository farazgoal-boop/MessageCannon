"""DB-level coverage for get_email_stats_since (Item 6, final completion
pass) -- the real sent/failed counts the reputation indicator's
failure-rate signal is built from. Uses a throwaway temp-file SQLite
database, never the real user database."""

from datetime import date, datetime, time, timedelta

from src.database.db_manager import DatabaseManager
from src.models import MessageLog, MessageStatus


def _make_db(tmp_path):
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = str(tmp_path / "reputation_test.db")
    db._initialize_database()
    return db


def test_counts_sent_and_failed_within_window(tmp_path):
    db = _make_db(tmp_path)
    today = date.today()

    for i in range(7):
        db.add_message_log(MessageLog(
            contact_email=f"s{i}@test.dev", message_text="hi", status=MessageStatus.SENT,
            sent_at=datetime.combine(today, time(9, 0))))
    for i in range(3):
        db.add_message_log(MessageLog(
            contact_email=f"f{i}@test.dev", message_text="hi", status=MessageStatus.FAILED))

    stats = db.get_email_stats_since(today.strftime("%Y-%m-%d"))
    assert stats == {"sent": 7, "failed": 3}


def test_excludes_rows_older_than_the_window(tmp_path):
    db = _make_db(tmp_path)
    today = date.today()
    old = today - timedelta(days=30)

    with db.get_connection() as conn:
        conn.execute(
            "INSERT INTO message_logs (contact_email, message_text, status, created_at) "
            "VALUES (?, ?, ?, ?)",
            ("old@test.dev", "hi", "sent", old.strftime("%Y-%m-%d") + "T09:00:00"))
        conn.commit()

    stats = db.get_email_stats_since((today - timedelta(days=7)).strftime("%Y-%m-%d"))
    assert stats == {"sent": 0, "failed": 0}


def test_returns_zeros_when_nothing_logged(tmp_path):
    db = _make_db(tmp_path)
    assert db.get_email_stats_since(date.today().strftime("%Y-%m-%d")) == {"sent": 0, "failed": 0}

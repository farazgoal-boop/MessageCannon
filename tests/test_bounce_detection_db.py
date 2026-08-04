"""DB-level coverage for real bounce-delivery tracking (not just send-attempt
tracking) -- message_logs.bounced/bounce_reason/bounce_checked_at,
contacts.bounced, and the reconciliation/query methods built on top. Uses a
throwaway temp-file SQLite database, never the real user database."""

from src.database.db_manager import DatabaseManager
from src.models import Contact, MessageLog, MessageStatus


def _make_db(tmp_path):
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = str(tmp_path / "bounce_test.db")
    db._initialize_database()
    return db


def test_schema_has_bounce_columns(tmp_path):
    db = _make_db(tmp_path)
    with db.get_connection() as conn:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(message_logs)").fetchall()]
        assert "bounced" in cols and "bounce_reason" in cols and "bounce_checked_at" in cols
        contact_cols = [r[1] for r in conn.execute("PRAGMA table_info(contacts)").fetchall()]
        assert "bounced" in contact_cols


def test_new_message_log_defaults_to_not_bounced(tmp_path):
    db = _make_db(tmp_path)
    log_id = db.add_message_log(MessageLog(
        contact_email="real@test.dev", message_text="hi", status=MessageStatus.SENT))
    logs = db.get_message_logs()
    assert logs[0].id == log_id
    assert logs[0].bounced is False
    assert logs[0].bounce_reason is None
    assert logs[0].bounce_checked_at is None


def test_mark_message_log_bounced_sets_flag_reason_and_timestamp_but_not_status(tmp_path):
    db = _make_db(tmp_path)
    log_id = db.add_message_log(MessageLog(
        contact_email="fake@test.dev", message_text="hi", status=MessageStatus.SENT))

    ok = db.mark_message_log_bounced(log_id, "550 5.1.1 User unknown")
    assert ok is True

    log = db.get_message_logs()[0]
    assert log.bounced is True
    assert log.bounce_reason == "550 5.1.1 User unknown"
    assert log.bounce_checked_at is not None
    # status stays SENT -- SMTP genuinely accepted it, and the existing
    # warm-up/daily-limit counters key off status='sent'; a later-confirmed
    # bounce must not retroactively corrupt those ledgers.
    assert log.status == MessageStatus.SENT


def test_get_sent_email_logs_for_bounce_check_excludes_failed_and_already_bounced(tmp_path):
    db = _make_db(tmp_path)
    campaign_id = db.add_campaign(__import__("src.models", fromlist=["Campaign"]).Campaign(
        name="Test Campaign", message_template="", total_contacts=3))

    sent_id = db.add_message_log(MessageLog(
        campaign_id=campaign_id, contact_email="pending-check@test.dev",
        message_text="hi", status=MessageStatus.SENT))
    db.add_message_log(MessageLog(
        campaign_id=campaign_id, contact_email="already-failed@test.dev",
        message_text="hi", status=MessageStatus.FAILED))
    already_bounced_id = db.add_message_log(MessageLog(
        campaign_id=campaign_id, contact_email="already-bounced@test.dev",
        message_text="hi", status=MessageStatus.SENT))
    db.mark_message_log_bounced(already_bounced_id, "prior check")

    candidates = db.get_sent_email_logs_for_bounce_check(campaign_id)
    emails = {c.contact_email for c in candidates}
    assert emails == {"pending-check@test.dev"}
    assert candidates[0].id == sent_id


def test_get_campaign_bounce_stats_reflects_reconciled_rows_only(tmp_path):
    db = _make_db(tmp_path)
    campaign_id = db.add_campaign(__import__("src.models", fromlist=["Campaign"]).Campaign(
        name="Test Campaign", message_template="", total_contacts=2))
    ok_id = db.add_message_log(MessageLog(
        campaign_id=campaign_id, contact_email="ok@test.dev", contact_name="Ok Person",
        message_text="hi", status=MessageStatus.SENT))
    bad_id = db.add_message_log(MessageLog(
        campaign_id=campaign_id, contact_email="bad@test.dev", contact_name="Bad Person",
        message_text="hi", status=MessageStatus.SENT))

    stats_before = db.get_campaign_bounce_stats(campaign_id)
    assert stats_before == {"bounced_count": 0, "bounced": []}

    db.mark_message_log_bounced(bad_id, "mailbox does not exist")
    stats_after = db.get_campaign_bounce_stats(campaign_id)
    assert stats_after["bounced_count"] == 1
    assert stats_after["bounced"] == [("Bad Person", "bad@test.dev", "mailbox does not exist")]


def test_recent_campaigns_summary_includes_real_bounced_count(tmp_path):
    db = _make_db(tmp_path)
    campaign_id = db.add_campaign(__import__("src.models", fromlist=["Campaign"]).Campaign(
        name="Summary Campaign", message_template="", total_contacts=2, sent_count=2))
    good_id = db.add_message_log(MessageLog(
        campaign_id=campaign_id, contact_email="good@test.dev", message_text="hi",
        status=MessageStatus.SENT))
    bad_id = db.add_message_log(MessageLog(
        campaign_id=campaign_id, contact_email="bad@test.dev", message_text="hi",
        status=MessageStatus.SENT))
    db.mark_message_log_bounced(bad_id, "no such user")

    summary = db.get_recent_campaigns_summary(limit=10)
    row = next(r for r in summary if r["id"] == campaign_id)
    assert row["bounced_count"] == 1
    assert row["sent_count"] == 2  # unchanged -- SMTP-accept count, not delivery count


def test_set_contact_bounced_by_id(tmp_path):
    db = _make_db(tmp_path)
    contact_id = db.add_contact(Contact(phone="+15551230001", email="c1@test.dev", name="C1"))
    assert db.set_contact_bounced(contact_id, True) is True
    contact = db.get_contacts()[0]
    assert contact.bounced is True

    assert db.set_contact_bounced(contact_id, False) is True
    contact = db.get_contacts()[0]
    assert contact.bounced is False


def test_set_contact_bounced_by_email_is_case_insensitive_and_only_matches_real_rows(tmp_path):
    db = _make_db(tmp_path)
    db.add_contact(Contact(phone="+15551230002", email="Real@Test.dev", name="Real"))

    matched = db.set_contact_bounced_by_email("real@test.dev", True)
    assert matched is True
    contact = db.get_contacts()[0]
    assert contact.bounced is True

    unmatched = db.set_contact_bounced_by_email("nobody-like-this@test.dev", True)
    assert unmatched is False


def test_contact_default_bounced_is_false(tmp_path):
    db = _make_db(tmp_path)
    db.add_contact(Contact(phone="+15551230003", email="fresh@test.dev", name="Fresh"))
    contact = db.get_contacts()[0]
    assert contact.bounced is False

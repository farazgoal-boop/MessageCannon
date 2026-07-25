"""Regression coverage for Item 2 of the Live Testing Findings pass: a
contact with a valid email but no phone must import successfully (as
email-eligible), not get wrongly marked "Invalid". Covers both the DB-level
phone-nullable migration and the ContactManager analyze/commit flow.

Real bug this closes: `contacts.phone` was NOT NULL on any database created
under an older schema version (CREATE TABLE IF NOT EXISTS never retrofits an
existing table), so email-only rows always failed to insert -- previously
"fixed" by rejecting them at the UI layer with a "phone required" message
instead of fixing the actual constraint. `_migrate_contacts_phone_nullable`
rebuilds the table without the constraint; `analyze_import`/`commit_import`
now treat "has phone OR email" as valid.
"""

from __future__ import annotations

import sqlite3

from src.core.contact_manager import ContactManager
from src.database.db_manager import DatabaseManager


def _fresh_db(tmp_path, name="contacts_test.db"):
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = str(tmp_path / name)
    db._initialize_database()
    return db


def _make_old_schema_db(tmp_path, name="legacy.db") -> str:
    """A throwaway DB built with the OLD (NOT NULL phone) schema, simulating
    a real, already-deployed database from before this app made phone
    nullable -- the exact scenario `_migrate_contacts_phone_nullable` exists
    to fix."""
    path = str(tmp_path / name)
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            phone TEXT NOT NULL UNIQUE,
            email TEXT,
            name TEXT,
            tags TEXT,
            custom_fields TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            opted_out INTEGER DEFAULT 0
        );
    """)
    conn.execute(
        "INSERT INTO contacts (phone, email, name, tags, custom_fields) VALUES (?,?,?,?,?)",
        ("+15551234567", "real@example.com", "Real Contact", "", "{}"))
    conn.commit()
    conn.close()
    return path


def test_migration_drops_not_null_and_preserves_data(tmp_path):
    path = _make_old_schema_db(tmp_path)
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = path
    db._initialize_database()  # runs _run_migrations -> _migrate_contacts_phone_nullable

    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(contacts)")
        phone_col = next(r for r in cursor.fetchall() if r[1] == "phone")
        assert phone_col[3] == 0  # notnull flag cleared

        cursor.execute("SELECT phone, email, name FROM contacts")
        rows = cursor.fetchall()
        assert len(rows) == 1
        assert rows[0][0] == "+15551234567"
        assert rows[0][1] == "real@example.com"
        assert rows[0][2] == "Real Contact"


def test_migration_backs_up_file_before_rebuilding(tmp_path):
    path = _make_old_schema_db(tmp_path)
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = path
    db._initialize_database()

    from pathlib import Path
    assert Path(f"{path}.pre-phone-migration.bak").exists()


def test_migration_is_idempotent_noop_on_already_nullable_schema(tmp_path):
    db = _fresh_db(tmp_path)  # built from the current (already-nullable) schema
    db._migrate_contacts_phone_nullable()  # must not raise or touch anything
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(contacts)")
        phone_col = next(r for r in cursor.fetchall() if r[1] == "phone")
        assert phone_col[3] == 0


def test_multiple_email_only_contacts_can_coexist_after_migration(tmp_path):
    """The actual point of storing NULL instead of '' for a missing phone --
    UNIQUE allows many NULLs but only one ''."""
    path = _make_old_schema_db(tmp_path)
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = path
    db._initialize_database()

    id1 = db.add_contact(_contact(phone="", email="a@test.dev", name="A"))
    id2 = db.add_contact(_contact(phone="", email="b@test.dev", name="B"))
    assert id1 is not None
    assert id2 is not None

    contacts = db.get_contacts()
    emails = {c.email for c in contacts}
    assert "a@test.dev" in emails and "b@test.dev" in emails


def _contact(phone, email, name):
    from src.models import Contact
    return Contact(phone=phone, email=email, name=name)


def _make_contact_manager(db) -> ContactManager:
    """Bypasses ContactManager.__init__ entirely -- it calls bare
    DatabaseManager(), which (via the real singleton `__new__`) can init
    against the REAL production database path the first time it's ever
    constructed in this process. Every other test in this file already
    avoids that for DatabaseManager itself (`DatabaseManager.__new__`);
    ContactManager needs the same treatment since it wraps one."""
    from src.utils.validators import PhoneValidator
    cm = ContactManager.__new__(ContactManager)
    cm.db = db
    cm.phone_validator = PhoneValidator()
    return cm


def _write_csv(tmp_path, rows) -> str:
    path = tmp_path / "import.csv"
    lines = ["name,phone,email"]
    for name, phone, email in rows:
        lines.append(f"{name},{phone},{email}")
    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def test_analyze_import_classifies_by_channel_eligibility(tmp_path):
    csv_path = _write_csv(tmp_path, [
        ("Email Only", "", "email.only@test.dev"),
        ("Phone Only", "+15551110001", ""),
        ("Both", "+15551110002", "both@test.dev"),
        ("Neither", "", "not-an-email"),
    ])

    cm = _make_contact_manager(_fresh_db(tmp_path))

    analysis = cm.analyze_import(csv_path)
    rows = {r["name"]: r for r in analysis["rows"]}

    assert rows["Email Only"]["status"] == "valid"
    assert rows["Email Only"]["channel"] == "email"
    assert rows["Email Only"]["phone"] == ""

    assert rows["Phone Only"]["status"] == "valid"
    assert rows["Phone Only"]["channel"] == "whatsapp"

    assert rows["Both"]["status"] == "valid"
    assert rows["Both"]["channel"] == "both"

    assert rows["Neither"]["status"] == "invalid"


def test_commit_import_actually_saves_email_only_contacts(tmp_path):
    """The literal repro of the reported bug: 12 email-only contacts should
    all import successfully, not get skipped as invalid."""
    rows_in = [("Email Only", "", f"user{i}@test.dev") for i in range(12)]
    csv_path = _write_csv(tmp_path, rows_in)

    cm = _make_contact_manager(_fresh_db(tmp_path))

    analysis = cm.analyze_import(csv_path)
    assert all(r["status"] == "valid" and r["channel"] == "email" for r in analysis["rows"])

    result = cm.commit_import(analysis["rows"])
    assert result["imported"] == 12
    assert result["skipped_invalid"] == 0

    saved = cm.db.get_contacts()
    assert len(saved) == 12
    assert all(c.phone == "" for c in saved)
    assert {c.email for c in saved} == {f"user{i}@test.dev" for i in range(12)}


def test_commit_import_merge_by_email_for_phoneless_duplicate(tmp_path):
    cm = _make_contact_manager(_fresh_db(tmp_path))
    cm.db.add_contact(_contact(phone="", email="dup@test.dev", name=""))

    csv_path = _write_csv(tmp_path, [("New Name", "", "dup@test.dev")])
    analysis = cm.analyze_import(csv_path)
    row = analysis["rows"][0]
    assert row["status"] == "dup_in_db"

    result = cm.commit_import(analysis["rows"], dup_resolution="merge")
    assert result["merged"] == 1

    saved = cm.db.get_contacts()
    assert len(saved) == 1
    assert saved[0].name == "New Name"  # filled the existing blank name

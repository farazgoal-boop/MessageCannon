"""Multi-number WhatsApp account groundwork (Item 7, final completion
pass) -- account CRUD, slugify/directory-collision handling, and the
round-robin rotation algorithm. All against a throwaway temp-file
DatabaseManager, never the real user database.

Real send-loop rotation against a real second WhatsApp-registered phone
cannot be verified in this environment -- see the module docstring in
src/core/whatsapp_accounts.py. These tests cover the mechanism that IS
verifiable here: account storage and the rotation algorithm itself.
"""

import pytest

from src.core import whatsapp_accounts as WA


def _make_db(tmp_path):
    from src.database.db_manager import DatabaseManager
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = str(tmp_path / "whatsapp_accounts_test.db")
    db._initialize_database()
    return db


def test_list_accounts_empty_by_default(tmp_path):
    db = _make_db(tmp_path)
    assert WA.list_accounts(db) == []


def test_add_account_persists_and_is_listed(tmp_path):
    db = _make_db(tmp_path)
    account = WA.add_account(db, "Sales Line")
    assert account.label == "Sales Line"
    assert account.session_dir_name == "sales_line"

    accounts = WA.list_accounts(db)
    assert len(accounts) == 1
    assert accounts[0].label == "Sales Line"


def test_add_account_rejects_empty_label(tmp_path):
    db = _make_db(tmp_path)
    with pytest.raises(ValueError):
        WA.add_account(db, "   ")


def test_add_account_rejects_case_insensitive_duplicate(tmp_path):
    db = _make_db(tmp_path)
    WA.add_account(db, "Support Line")
    with pytest.raises(ValueError):
        WA.add_account(db, "support line")


def test_add_account_disambiguates_colliding_directory_slugs(tmp_path):
    db = _make_db(tmp_path)
    a = WA.add_account(db, "Sales!!")
    b = WA.add_account(db, "Sales??")  # slugifies to the same base as above
    assert a.session_dir_name == "sales"
    assert b.session_dir_name == "sales_2"


def test_remove_account_returns_false_for_unknown_label(tmp_path):
    db = _make_db(tmp_path)
    assert WA.remove_account(db, "Nope") is False


def test_remove_account_removes_only_the_matching_one(tmp_path):
    db = _make_db(tmp_path)
    WA.add_account(db, "Sales")
    WA.add_account(db, "Support")
    assert WA.remove_account(db, "Sales") is True
    remaining = WA.list_accounts(db)
    assert len(remaining) == 1
    assert remaining[0].label == "Support"


def test_get_account_session_dir_is_isolated_per_account(tmp_path, monkeypatch):
    from src.utils import paths as paths_module
    monkeypatch.setattr(paths_module, "get_session_dir", lambda: tmp_path / "shared_session_root")

    db = _make_db(tmp_path)
    a = WA.add_account(db, "Sales")
    b = WA.add_account(db, "Support")

    dir_a = WA.get_account_session_dir(a)
    dir_b = WA.get_account_session_dir(b)

    assert dir_a != dir_b
    assert dir_a.exists() and dir_b.exists()
    assert dir_a.parent == dir_b.parent  # both nested under the same shared root


def test_assign_account_returns_none_with_no_accounts_configured():
    # Falls back to the single default session -- exactly today's real,
    # working, single-account behavior.
    assert WA.assign_account_for_message([], message_index=0, messages_per_account=10) is None


def test_assign_account_rotates_every_n_messages():
    accounts = [WA.WhatsAppAccount(label="A", session_dir_name="a"),
                WA.WhatsAppAccount(label="B", session_dir_name="b"),
                WA.WhatsAppAccount(label="C", session_dir_name="c")]

    assignments = [WA.assign_account_for_message(accounts, i, messages_per_account=5).label
                   for i in range(16)]

    assert assignments[0:5] == ["A"] * 5
    assert assignments[5:10] == ["B"] * 5
    assert assignments[10:15] == ["C"] * 5
    assert assignments[15] == "A"  # wraps back around after all accounts have had a turn


def test_assign_account_treats_non_positive_messages_per_account_as_one():
    accounts = [WA.WhatsAppAccount(label="A", session_dir_name="a"),
                WA.WhatsAppAccount(label="B", session_dir_name="b")]
    assignments = [WA.assign_account_for_message(accounts, i, messages_per_account=0).label
                   for i in range(4)]
    assert assignments == ["A", "B", "A", "B"]

"""Coverage for SessionManager's account_label parameter (Item 7, final
completion pass) -- the single most important thing to verify about this
change: that the DEFAULT (no account_label) path is byte-for-byte
identical to before, since every real call site in this app today
constructs SessionManager() with no argument, reading/writing the live
production database's existing "whatsapp_session_state" key. Uses a
throwaway temp-file DatabaseManager, never the real user database.
"""

from src.session_manager import SessionManager


def _make_db(tmp_path):
    from src.database.db_manager import DatabaseManager
    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = str(tmp_path / "session_manager_test.db")
    db._initialize_database()
    return db


def test_default_session_key_unchanged_from_before_this_change(tmp_path, monkeypatch):
    from src import session_manager as sm_module
    monkeypatch.setattr(sm_module, "DatabaseManager", lambda: _make_db(tmp_path))

    mgr = SessionManager(session_dir=tmp_path / "session")
    assert mgr.session_key == "whatsapp_session_state" == SessionManager.SESSION_KEY


def test_account_label_namespaces_the_session_key(tmp_path, monkeypatch):
    from src import session_manager as sm_module
    monkeypatch.setattr(sm_module, "DatabaseManager", lambda: _make_db(tmp_path))

    mgr = SessionManager(session_dir=tmp_path / "session", account_label="sales_line")
    assert mgr.session_key == "whatsapp_session_state_sales_line"
    assert mgr.session_key != SessionManager.SESSION_KEY


def test_two_accounts_do_not_share_session_state(tmp_path, monkeypatch):
    from src import session_manager as sm_module
    db = _make_db(tmp_path)
    monkeypatch.setattr(sm_module, "DatabaseManager", lambda: db)

    mgr_a = SessionManager(session_dir=tmp_path / "a", account_label="account_a")
    mgr_b = SessionManager(session_dir=tmp_path / "b", account_label="account_b")

    mgr_a.mark_session_verified()

    state_a = mgr_a._read_state()
    state_b = mgr_b._read_state()

    assert state_a["last_verified_at"] != ""
    assert state_b["last_verified_at"] == "", (
        "marking account A's session verified must not leak into account B's "
        "independently-tracked session state")


def test_default_session_manager_state_untouched_by_a_named_account(tmp_path, monkeypatch):
    """The exact backward-compatibility guarantee this change depends on:
    a real, existing default SessionManager() (no account_label -- what
    every current call site in main_window.py actually constructs) must
    read/write the identical key whether or not any named accounts exist
    elsewhere in the same database."""
    from src import session_manager as sm_module
    db = _make_db(tmp_path)
    monkeypatch.setattr(sm_module, "DatabaseManager", lambda: db)

    default_mgr = SessionManager(session_dir=tmp_path / "default")
    default_mgr.mark_session_verified()
    default_state_before = default_mgr._read_state()

    named_mgr = SessionManager(session_dir=tmp_path / "named", account_label="second_number")
    named_mgr.mark_session_verified()

    default_state_after = default_mgr._read_state()
    assert default_state_after == default_state_before, (
        "creating a named account's SessionManager must not alter the "
        "default (no-account) SessionManager's own session state")

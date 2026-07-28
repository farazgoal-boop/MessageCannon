"""Real bug found via a live end-to-end email send test (2026-07-29): the
real production settings had a literal trailing newline in `smtp_from_addr`
("ikrashikrama398@gmail.com\\n") -- almost certainly from a clipboard paste
into the Settings field, since a plain CTkEntry doesn't let you *type* a
newline but does accept one pasted in. `_load_settings`/`_save_settings`
never stripped these SMTP fields, so the stray newline reached smtplib's
real "From" header construction unstripped and every single email send
failed with `email.errors.HeaderParseError: folded header contains
newline`. Reproduced live: a real send to farazgoal@gmail.com failed with
exactly that error before the fix, and succeeded (1 sent, 0 failed) after
it -- see CLAUDE.md's own checkpoint for the full account. This file locks
in the fix with automated coverage in addition to that one-off live proof.

Uses a dedicated, module-scoped, fresh-DB MainWindow (same pattern as
test_email_warmup_enforcement.py) so writing a deliberately-corrupted
settings blob never touches the real production database.
"""

import tkinter as tk

import pytest


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
    fresh_db_path = str(tmp_path_factory.mktemp("smtp_whitespace") / "test.db")
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


def test_load_settings_strips_stray_whitespace_from_smtp_fields(window):
    """The literal repro: a stored settings blob with a trailing newline in
    smtp_from_addr (and a trailing space in smtp_from_name, the other real
    field found corrupted in production) must come out clean after load."""
    window.db.set_setting_json(window.SETTINGS_KEY, {
        "smtp_provider": "Gmail",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": "587",
        "smtp_user": "sender@gmail.com",
        "smtp_from_name": "Faraz Automation ",
        "smtp_from_addr": "sender@gmail.com\n",
        "smtp_delay": "5",
    })

    window._load_settings()

    assert window._em_from_addr.get() == "sender@gmail.com"
    assert window._em_from_name.get() == "Faraz Automation"
    assert window._em_user.get() == "sender@gmail.com"
    assert "\n" not in window._em_from_addr.get()


def test_save_settings_persists_stripped_values_not_raw_input(window):
    """Even if a live Settings entry currently holds an untrimmed value
    (e.g. right after a fresh paste, before any reload), saving must not
    write the raw, still-corrupted string back to disk."""
    original_addr = window._em_from_addr.get()
    original_name = window._em_from_name.get()
    try:
        window._em_from_addr.set("pasted@gmail.com\n")
        window._em_from_name.set("  Some Business  ")

        window._save_settings()

        stored = window.db.get_setting_json(window.SETTINGS_KEY, {})
        assert stored["smtp_from_addr"] == "pasted@gmail.com"
        assert stored["smtp_from_name"] == "Some Business"
    finally:
        window._em_from_addr.set(original_addr)
        window._em_from_name.set(original_name)
        window._save_settings()


def test_from_header_construction_no_longer_raises_with_previously_corrupted_value(window):
    """The actual, real-world crash site: email.mime.text.MIMEText's header
    folding raises HeaderParseError on a raw embedded newline. Confirms the
    exact "From" header this app builds in _send_email_campaign no longer
    contains one once the value has gone through _load_settings/_save_settings."""
    from email.mime.text import MIMEText

    window.db.set_setting_json(window.SETTINGS_KEY, {
        "smtp_from_name": "Faraz Automation ",
        "smtp_from_addr": "sender@gmail.com\n",
    })
    window._load_settings()

    msg = MIMEText("<p>hi</p>", "html")
    msg["From"] = f"{window._em_from_name.get()} <{window._em_from_addr.get()}>"
    # Must not raise -- this is exactly what failed live before the fix.
    msg.as_string()

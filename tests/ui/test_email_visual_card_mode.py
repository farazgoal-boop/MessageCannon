""""Send as Visual HTML Card" mode (Live Testing Findings, 2026-07-29) --
Card Creator's Insert-into-Compose can now offer the real generated card
HTML as the actual email body (locked/read-only in Compose) instead of
always flattening it into the rich-text editor. Covers:

- _enter_email_card_mode locks the editor/toolbar and shows the lock panel;
  _exit_email_card_mode reverses it and flattens the card back into the
  rich-text editor as a courtesy.
- _start_email_from_compose sends the real card HTML (not a rich-text
  export) when in card mode, with {variable} tokens substituted per
  recipient exactly like any other email template.
- The confirmation-dialog preview text is real, readable text (not raw
  HTML tags) via _strip_html_for_preview.

Uses a dedicated, module-scoped, fresh-DB MainWindow (same pattern as
test_email_warmup_enforcement.py) -- no real SMTP/network involved.
"""

import tkinter as tk

import pytest

from src.models import Contact


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
    fresh_db_path = str(tmp_path_factory.mktemp("email_card_mode") / "test.db")
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
def _reset_card_mode(window):
    """Every test gets a clean, unlocked editor to start from, with Compose
    (Email channel) the actually-visible view -- winfo_ismapped() on any
    Compose descendant is only meaningful once its ancestor view container
    is itself shown via _show_view, not just grid()'d locally."""
    if window._compose_card_mode:
        window._exit_email_card_mode()
    window._compose_em_body.delete("1.0", "end")
    window._compose_em_body.insert("1.0", "Dear {name},\n\nYour message here.")
    window._show_view("Compose")
    window._compose_channel_var.set("Email")
    window._on_channel_switch("Email")
    window.update()
    yield
    if window._compose_card_mode:
        window._exit_email_card_mode()


SAMPLE_CARD_HTML = (
    "<html><body>"
    "<div><span>{name}</span></div>"
    "<div><span>$299</span><span>$599</span><span>50% OFF</span></div>"
    "</body></html>"
)


def test_enter_card_mode_locks_editor_and_shows_lock_panel(window):
    window._enter_email_card_mode(SAMPLE_CARD_HTML, "My Card Subject")
    window.update()

    assert window._compose_card_mode is True
    assert window._compose_card_html_template == SAMPLE_CARD_HTML
    assert window._em_subj_var.get() == "My Card Subject"
    assert not window._compose_em_body.winfo_ismapped()
    assert window._em_card_lock_frame.winfo_ismapped()
    assert str(window._em_fmt_bold_btn.cget("state")) == "disabled"
    assert str(window.em_template_menu.cget("state")) == "disabled"


def test_exit_card_mode_unlocks_editor_and_flattens_card_back_in(window):
    window._enter_email_card_mode(SAMPLE_CARD_HTML, "My Card Subject")
    window.update()

    window._exit_email_card_mode()
    window.update()

    assert window._compose_card_mode is False
    assert window._compose_card_html_template == ""
    assert window._compose_em_body.winfo_ismapped()
    assert not window._em_card_lock_frame.winfo_ismapped()
    assert str(window._em_fmt_bold_btn.cget("state")) == "normal"
    # The real card content should have been flattened back into the editor
    # as a courtesy, not left empty.
    body_text = window._get_text_with_tokens(window._compose_em_body)
    assert "{name}" in body_text or "name" in body_text.lower()


def test_start_email_from_compose_sends_real_card_html_with_substitution(window, monkeypatch):
    """The literal end-to-end proof: entering card mode and starting a send
    must carry the real generated card HTML through to the actual per-
    recipient send list, with {name} substituted -- not the rich-text
    editor's own (irrelevant, locked) content."""
    from src.ui import send_dialogs

    original_contacts = window.contacts
    original_thread = window._em_send_thread
    captured = {}

    def fake_confirmation(main_window, channel, count, delay, preview_lines,
                           on_confirm=None, subject=None, quality_flag_count=0, **kwargs):
        captured["preview_lines"] = preview_lines
        captured["subject"] = subject
        captured["exclusions_note"] = kwargs.get("exclusions_note", "")
        if on_confirm:
            on_confirm()

    def fake_execute_email_send(recipients):
        captured["recipients"] = recipients

    try:
        window.contacts = [
            Contact(id=1, name="Priya", phone="+10000000001", email="priya@test.dev"),
        ]
        window._em_user.set("sender@test.dev")
        window._em_pass.set("app-password")
        window.email_warmup_enabled_var.set(False)

        window._enter_email_card_mode(SAMPLE_CARD_HTML, "Card for {name}")
        window.update()

        monkeypatch.setattr(send_dialogs, "show_send_confirmation", fake_confirmation)
        monkeypatch.setattr(window, "_execute_email_send", fake_execute_email_send)

        window._start_email_from_compose()
        window.update()

        assert "recipients" in captured, "on_confirm was never invoked"
        # Recipients are now (contact, subject, html_body, plain_body) 4-tuples
        # — the plain_body part was added so the SMTP message can carry a real
        # text/plain alternative alongside text/html.
        contact, subject, html_body, plain_body = captured["recipients"][0]
        assert subject == "Card for Priya"
        assert "Priya" in html_body
        assert "{name}" not in html_body
        # The real card structure (price row) must be the actual generated
        # HTML, not a rich-text re-export of the locked editor's content.
        assert "$299" in html_body and "50% OFF" in html_body
        # The preview text shown in the confirmation dialog must be real,
        # readable text, not raw HTML tags.
        assert "<div>" not in captured["preview_lines"][0]
        assert "<span>" not in captured["preview_lines"][0]
        assert "Priya" in captured["preview_lines"][0]
    finally:
        window.contacts = original_contacts
        window._em_send_thread = original_thread


def test_strip_html_for_preview_produces_readable_text(window):
    text = window._strip_html_for_preview(SAMPLE_CARD_HTML)
    assert "<" not in text
    assert "$299" in text and "50% OFF" in text

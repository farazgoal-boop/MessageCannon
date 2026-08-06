"""Item 34 of the multi-product generalization pass: pushing the AI
features further. UI-level coverage for the 5 sub-items -- the pure-logic
pieces (send_time_advisor, contact_quality, and the 3 new ai_service
functions) already have their own fast, non-UI test files.
"""

from __future__ import annotations

import customtkinter as ctk

from src.core.ai_service import AIServiceError
from src.ui.send_dialogs import SendConfirmationDialog, SendReportDialog


class _SynchronousThread:
    """Stand-in for threading.Thread that runs the target immediately, on
    the calling (main) thread. Needed because this test harness drives the
    app via `app.update()` polling rather than a real `mainloop()` --
    cross-thread `self.after()` registration requires Tcl to consider
    itself "in" a running mainloop, which manual `update()` polling never
    establishes (same documented harness limitation already worked around
    in test_ai_error_reporting.py/test_update_dialog_e2e.py). Only the
    concurrency, not the real logic under test, is stubbed."""

    def __init__(self, target=None, daemon=None, **_kwargs):
        self._target = target

    def start(self):
        self._target()


def _destroy(widget) -> None:
    try:
        if widget.winfo_exists():
            widget.destroy()
    except Exception:
        pass


# ── Sub-items 2 + 4: send-time recommendation + contact quality note in
# the pre-send confirmation dialog ─────────────────────────────────────────

def test_confirmation_dialog_shows_send_time_recommendation(app):
    dlg = SendConfirmationDialog(
        app, "email", 5, 3.0, ["preview"], on_confirm=lambda: None)
    app.update()
    try:
        found = _find_label_containing(dlg, "Best time to send")
        assert found is not None
    finally:
        _destroy(dlg)


def test_confirmation_dialog_hides_quality_note_when_zero(app):
    dlg = SendConfirmationDialog(
        app, "email", 5, 3.0, ["preview"], on_confirm=lambda: None, quality_flag_count=0)
    app.update()
    try:
        assert _find_label_containing(dlg, "role-based addresses") is None
    finally:
        _destroy(dlg)


def test_confirmation_dialog_shows_quality_note_when_flags_present(app):
    dlg = SendConfirmationDialog(
        app, "email", 5, 3.0, ["preview"], on_confirm=lambda: None, quality_flag_count=2)
    app.update()
    try:
        found = _find_label_containing(dlg, "role-based addresses")
        assert found is not None
        assert "2 recipient" in found
    finally:
        _destroy(dlg)


def _find_label_containing(widget, needle: str):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            text = child.cget("text")
            if needle in text:
                return text
        found = _find_label_containing(child, needle)
        if found is not None:
            return found
    return None


# ── Sub-item 5: AI campaign performance summary ────────────────────────────

def test_report_dialog_shows_ai_summary_button_only_when_callback_given(app):
    dlg_without = SendReportDialog(app, "email", 10, 0, [])
    app.update()
    try:
        assert not hasattr(dlg_without, "_ai_summary_btn")
    finally:
        _destroy(dlg_without)

    dlg_with = SendReportDialog(app, "email", 10, 0, [], on_ai_summary=lambda cb: None)
    app.update()
    try:
        assert dlg_with._ai_summary_btn.winfo_exists()
        assert dlg_with._ai_summary_btn.cget("text") == "🤖 AI Summary"
    finally:
        _destroy(dlg_with)


def test_report_dialog_ai_summary_button_click_invokes_callback_and_shows_result(app):
    captured = {}

    def fake_on_ai_summary(dialog_callback):
        captured["called"] = True
        dialog_callback(True, "Solid campaign: 10 sent, 0 bounced.", "")

    dlg = SendReportDialog(app, "email", 10, 0, [], on_ai_summary=fake_on_ai_summary)
    app.update()
    try:
        dlg._run_ai_summary()
        app.update()
        assert captured.get("called") is True
        # A result Toplevel should now exist showing the real summary text.
        found = False
        for child in app.winfo_children():
            pass  # result dialog is a child of `dlg`, not `app`
        for child in dlg.winfo_children():
            if isinstance(child, ctk.CTkToplevel):
                found = True
        assert found, "expected a real result Toplevel after a successful AI summary"
    finally:
        _destroy(dlg)


def test_request_ai_campaign_summary_grounds_in_real_stats_not_invented(app, monkeypatch):
    captured = {}

    def fake_summarize(stats, api_key, provider="anthropic"):
        captured["stats"] = stats
        return "Real summary text."

    monkeypatch.setattr("src.ui.main_window.ai_service.summarize_campaign_performance", fake_summarize)
    monkeypatch.setattr("src.ui.main_window.threading.Thread", _SynchronousThread)
    original_key = app._ai_api_key.get()
    app._ai_api_key.set("test-key")
    try:
        results = []
        app._request_ai_campaign_summary(
            campaign_name="Real Campaign", sent=42, failed=3, bounced=1,
            dialog_callback=lambda ok, summary, err: results.append((ok, summary, err)))
        deadline_updates = 0
        while not results and deadline_updates < 50:
            app.update()
            deadline_updates += 1
        assert results and results[0][0] is True
        assert results[0][1] == "Real summary text."
        assert captured["stats"] == {
            "campaign_name": "Real Campaign", "total_sent": 42, "failed": 3, "bounced": 1,
        }
    finally:
        app._ai_api_key.set(original_key)


def test_request_ai_campaign_summary_requires_a_real_api_key(app):
    original_key = app._ai_api_key.get()
    app._ai_api_key.set("")
    try:
        results = []
        app._request_ai_campaign_summary(
            campaign_name="X", sent=1, failed=0, bounced=0,
            dialog_callback=lambda ok, summary, err: results.append((ok, summary, err)))
        assert results == [(False, "", "Add an AI API key in Settings first.")]
    finally:
        app._ai_api_key.set(original_key)


# ── Sub-item 1: AI subject-line optimizer ──────────────────────────────────

def test_subject_optimize_button_exists_in_compose(app):
    assert hasattr(app, "_subject_optimize_btn")
    assert app._subject_optimize_btn.winfo_exists()


def test_open_subject_optimizer_requires_a_real_body(app, monkeypatch):
    shown = {}
    monkeypatch.setattr(
        "src.ui.main_window.messagebox.showwarning",
        lambda title, msg: shown.update(title=title, msg=msg))
    original_key = app._ai_api_key.get()
    app._ai_api_key.set("test-key")
    original_body = app._compose_em_body.get("1.0", "end")
    try:
        app._compose_em_body.delete("1.0", "end")
        app._open_subject_optimizer()
        assert shown.get("title") == "Nothing to optimize"
    finally:
        app._ai_api_key.set(original_key)
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", original_body)


def test_open_subject_optimizer_end_to_end_shows_real_suggestions(app, monkeypatch):
    def fake_generate_subject_lines(body, api_key, provider="anthropic"):
        assert "real body" in body
        return [{"subject": "Great deal inside", "rationale": "curiosity"}]

    monkeypatch.setattr(
        "src.ui.main_window.ai_service.generate_subject_lines", fake_generate_subject_lines)
    monkeypatch.setattr("src.ui.main_window.threading.Thread", _SynchronousThread)
    original_key = app._ai_api_key.get()
    app._ai_api_key.set("test-key")
    original_body = app._compose_em_body.get("1.0", "end")
    try:
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", "This is the real body of my email.")
        app._open_subject_optimizer()
        deadline_updates = 0
        while app._subject_optimize_btn.cget("state") == "disabled" and deadline_updates < 50:
            app.update()
            deadline_updates += 1
        app.update()

        found_dialog = None
        for child in app.winfo_children():
            if isinstance(child, ctk.CTkToplevel) and child.title() == "Subject Line Suggestions":
                found_dialog = child
        assert found_dialog is not None
        found_dialog.destroy()
    finally:
        app._ai_api_key.set(original_key)
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", original_body)


# ── Sub-item 3: A/B variant generation in AIComposeDialog ──────────────────

def test_ai_compose_dialog_has_ab_mode_checkbox(app):
    from src.ui.ai_compose_dialog import AIComposeDialog
    dlg = AIComposeDialog(app, "email", on_pick=lambda text, subject: None)
    app.update()
    try:
        assert hasattr(dlg, "_ab_mode_var")
        assert dlg._ab_mode_var.get() is False
    finally:
        _destroy(dlg)


def test_ai_compose_dialog_ab_mode_calls_generate_ab_variants(app, monkeypatch):
    from src.ui.ai_compose_dialog import AIComposeDialog

    captured = {}

    def fake_ab_variants(brief, channel, api_key, angle_a="benefit-focused",
                          angle_b="urgency-focused", sample_variables=None, provider="anthropic"):
        captured["brief"] = brief
        captured["channel"] = channel
        return [
            {"angle": angle_a, "text": "Benefit message {name}", "subject": "Benefits"},
            {"angle": angle_b, "text": "Urgent message {name}", "subject": "Hurry"},
        ]

    monkeypatch.setattr("src.ui.ai_compose_dialog.ai_service.generate_ab_variants", fake_ab_variants)
    monkeypatch.setattr("src.ui.ai_compose_dialog.threading.Thread", _SynchronousThread)
    original_key = app._ai_api_key.get()
    app._ai_api_key.set("test-key")

    dlg = AIComposeDialog(app, "email", on_pick=lambda text, subject: None)
    app.update()
    try:
        dlg._ab_mode_var.set(True)
        dlg._brief_box.delete("1.0", "end")
        dlg._brief_box.insert("1.0", "Announce our summer sale.")
        dlg._generate()
        deadline_updates = 0
        while "brief" not in captured and deadline_updates < 50:
            app.update()
            deadline_updates += 1
        app.update()
        assert captured.get("brief") == "Announce our summer sale."
        # Both angle labels should now be rendered as real badge text.
        found_labels = _collect_label_texts(dlg)
        assert any("Benefit" in t for t in found_labels)
        assert any("Urgency" in t for t in found_labels)
    finally:
        app._ai_api_key.set(original_key)
        _destroy(dlg)


def _collect_label_texts(widget):
    texts = []
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            texts.append(child.cget("text"))
        texts.extend(_collect_label_texts(child))
    return texts


# ── Sub-item 4: quality flags actually reach the email confirmation dialog ─

def test_email_send_confirmation_receives_real_quality_flag_count(app, monkeypatch):
    """Confirms _start_email_from_compose actually computes and threads a
    real quality_flag_count through to show_send_confirmation -- driving
    the real, unmocked method end to end (only the SMTP send itself is
    never reached, since show_send_confirmation is intercepted before any
    network call) with one real role-based contact and one real normal
    contact, never touching the real contacts table."""
    from src.models import Contact

    original_contacts = app.contacts
    original_em_user = app._em_user.get()
    original_em_pass = app._em_pass.get()
    original_warmup = app.email_warmup_enabled_var.get()
    original_body = app._compose_em_body.get("1.0", "end")
    original_subject = app._em_subj_var.get()
    original_card_mode = app._compose_card_mode

    captured = {}

    def fake_show_send_confirmation(*args, **kwargs):
        captured["kwargs"] = kwargs
        captured["args"] = args
        return None

    monkeypatch.setattr("src.ui.send_dialogs.show_send_confirmation", fake_show_send_confirmation)

    try:
        app.contacts = [
            Contact(id=None, phone="", email="sarah@example.com", name="Sarah",
                    tags=[], custom_fields={}),
            Contact(id=None, phone="", email="info@example.com", name="Info Team",
                    tags=[], custom_fields={}),
        ]
        app._em_user.set("tester@example.com")
        app._em_pass.set("app-password")
        app.email_warmup_enabled_var.set(False)
        if original_card_mode:
            app._exit_email_card_mode()
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", "Hello {name}, real body.")
        app._em_subj_var.set("Real subject")

        app._start_email_from_compose()

        assert "kwargs" in captured, "show_send_confirmation was never called"
        assert captured["kwargs"]["quality_flag_count"] == 1
    finally:
        app.contacts = original_contacts
        app._em_user.set(original_em_user)
        app._em_pass.set(original_em_pass)
        app.email_warmup_enabled_var.set(original_warmup)
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", original_body)
        app._em_subj_var.set(original_subject)

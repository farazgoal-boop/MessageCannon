"""Item 10 of the Live Testing Findings pass: Compose general premium polish
-- (1) a real rich-text (Bold/Italic/List) email editor replacing the raw-
HTML-visible one, (2) 4 new ready-made email templates (Welcome/Promotion/
Reminder/Follow-up), (3) a live Preview panel for the Email tab, (4) a
clickable/expandable Recipients count, (5) a Subject line in the pre-send
confirmation summary.

Design decision recorded here (confirmed with the user before building):
the 4 pre-existing fancy HTML templates (Professional/Promo Offer/
Appointment Reminder/Invoice) get flattened into plain rich text via
_HTMLToRichText when picked -- Tk has no HTML-rendering widget, so real
WYSIWYG editing and preserving their gradients/colored-box/CTA-button
styling are mutually exclusive. Bold/italic/paragraph/bullet/link-URL
structure survives; visual chrome does not.
"""

from __future__ import annotations

import src.ui.main_window as mw_mod
from src.models import Contact


def _reset_em_editor(app) -> None:
    app._compose_em_body.delete("1.0", "end")
    app._compose_em_body.insert("1.0", "Dear {name},\n\nYour message here.")
    app._pillify_text_widget(app._compose_em_body)
    app._update_email_warnings()
    app.update()


def test_bold_toggle_exports_as_strong_not_literal_text(app):
    _reset_em_editor(app)
    try:
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", "Hello world")
        app._compose_em_body.tag_add("sel", "1.0", "1.5")  # "Hello"
        app._toggle_email_char_tag("b")
        app.update()

        html = app._email_rich_export_html(app._compose_em_body)
        assert "<strong>Hello</strong> world" in html
        raw = app._compose_em_body.get("1.0", "end")
        assert "<strong>" not in raw, "the tag must be a real Tk font tag, never literal text"
    finally:
        _reset_em_editor(app)


def test_italic_toggle_exports_as_em(app):
    _reset_em_editor(app)
    try:
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", "Hello world")
        app._compose_em_body.tag_add("sel", "1.6", "1.11")  # "world"
        app._toggle_email_char_tag("i")
        app.update()

        html = app._email_rich_export_html(app._compose_em_body)
        assert "Hello <em>world</em>" in html
    finally:
        _reset_em_editor(app)


def test_char_tag_toggle_is_a_true_toggle(app):
    _reset_em_editor(app)
    try:
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", "Hello world")
        app._compose_em_body.tag_add("sel", "1.0", "1.5")
        app._toggle_email_char_tag("b")
        app.update()
        assert "b" in app._compose_em_body.tag_names("1.0")

        app._compose_em_body.tag_add("sel", "1.0", "1.5")
        app._toggle_email_char_tag("b")
        app.update()
        assert "b" not in app._compose_em_body.tag_names("1.0")
    finally:
        _reset_em_editor(app)


def test_char_tag_toggle_is_a_noop_without_a_selection(app):
    _reset_em_editor(app)
    try:
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", "Hello world")
        app._toggle_email_char_tag("b")  # no selection -- must not raise or mutate
        app.update()
        assert app._compose_em_body.get("1.0", "end").strip() == "Hello world"
    finally:
        _reset_em_editor(app)


def test_bullet_toggle_wraps_line_in_ul_li_and_preserves_embedded_pill(app):
    """The bullet toggle must never lose a variable pill sitting on the same
    line -- the same class of risk _pillify_text_widget's own docstring
    already documents for any get/delete/insert round trip over a range
    containing an embedded window."""
    _reset_em_editor(app)
    try:
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", "{name}, welcome!")
        app._pillify_text_widget(app._compose_em_body)
        app.update()

        app._toggle_email_bullet_list()
        app.update()

        assert app._get_text_with_tokens(app._compose_em_body).strip() == "• {name}, welcome!"
        html = app._email_rich_export_html(app._compose_em_body)
        assert "<ul>" in html
        assert "<li>{name}, welcome!</li>" in html

        # Toggling again on the same line removes the bullet.
        app._toggle_email_bullet_list()
        app.update()
        assert app._get_text_with_tokens(app._compose_em_body).strip() == "{name}, welcome!"
    finally:
        _reset_em_editor(app)


def test_new_named_templates_are_plain_text_with_no_raw_html_tags(app):
    for name in ("Welcome", "Promotion", "Reminder", "Follow-up"):
        subj, body, is_html = mw_mod.EMAIL_TEMPLATES[name]
        assert is_html is False
        assert subj.strip() and body.strip()
        assert "<" not in body


def test_selecting_new_template_populates_editor_with_no_visible_tags(app):
    original_subj = app._em_subj_var.get()
    original_body = app._compose_em_body.get("1.0", "end")
    try:
        app.em_template_menu._command("Welcome")
        app.update()

        assert "Welcome aboard" in app._em_subj_var.get()
        raw = app._compose_em_body.get("1.0", "end")
        assert "<" not in raw
        assert "Welcome aboard" in raw
    finally:
        app._em_subj_var.set(original_subj)
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", original_body)
        app._update_email_warnings()
        app.update()


def test_selecting_a_legacy_html_template_flattens_via_importer_no_raw_tags(app):
    """Confirmed-with-user trade-off: the fancy "Promo Offer" template's
    gradients/CTA-button chrome is dropped, but its bold text and link URL
    must still survive as plain, visible content -- not as literal HTML."""
    original_subj = app._em_subj_var.get()
    original_body = app._compose_em_body.get("1.0", "end")
    try:
        app.em_template_menu._command("Promo Offer")
        app.update()

        raw = app._compose_em_body.get("1.0", "end")
        assert "<div" not in raw and "<strong>" not in raw and "<p>" not in raw
        assert "Special Offer" in raw
        assert "{name}" in app._get_text_with_tokens(app._compose_em_body) or "name" in raw.lower()
        # the bold "Hi {name}," text should have real bold formatting applied
        html = app._email_rich_export_html(app._compose_em_body)
        assert "<strong>" in html
    finally:
        app._em_subj_var.set(original_subj)
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", original_body)
        app._update_email_warnings()
        app.update()


def test_email_live_preview_substitutes_real_contact_data(app):
    original_contacts = app.contacts
    try:
        app.contacts = [Contact(id=9401, phone="", email="priya@test.dev", name="Priya")]
        _reset_em_editor(app)
        app.update()

        preview = app._em_preview_text.get("1.0", "end")
        assert "Priya" in preview
        assert "{name}" not in preview

        # No name on the contact -> the "To:" line falls back to the email
        # address, exercising the other half of `contact.name or contact.email`.
        app.contacts = [Contact(id=9401, phone="", email="priya@test.dev", name="")]
        _reset_em_editor(app)
        app.update()
        preview = app._em_preview_text.get("1.0", "end")
        assert "priya@test.dev" in preview
    finally:
        app.contacts = original_contacts
        _reset_em_editor(app)


def test_email_live_preview_empty_state_when_no_email_contacts(app):
    original_contacts = app.contacts
    try:
        app.contacts = [Contact(id=9402, phone="+15550009402", email="", name="NoEmail")]
        _reset_em_editor(app)
        app.update()

        preview = app._em_preview_text.get("1.0", "end")
        assert "Import a contact with an email address" in preview
    finally:
        app.contacts = original_contacts
        _reset_em_editor(app)


def test_recipients_list_dialog_shows_real_email_contacts(app):
    original_contacts = app.contacts
    try:
        app.contacts = [
            Contact(id=9403, phone="", email="a@test.dev", name="Contact A"),
            Contact(id=9404, phone="", email="b@test.dev", name="Contact B"),
        ]
        app._show_email_recipients_list()
        app.update()

        found = False
        for w in app.winfo_children():
            if w.winfo_class() != "Toplevel":
                continue
            text = _all_label_text(w)
            if "Contact A" in text and "a@test.dev" in text and "Contact B" in text:
                found = True
            w.destroy()
        assert found, "expected a real dialog listing the actual email contacts"
    finally:
        app.contacts = original_contacts


def _all_label_text(widget) -> str:
    text = ""
    try:
        text += str(widget.cget("text"))
    except Exception:
        pass
    for child in widget.winfo_children():
        text += _all_label_text(child)
    return text


def test_send_confirmation_dialog_shows_subject_row(app):
    from src.ui.send_dialogs import SendConfirmationDialog

    dlg = SendConfirmationDialog(
        app, "email", 3, 10.0, ["To: a@test.dev\nSubject: Hi\nBody"],
        on_confirm=lambda: None, subject="A real test subject line")
    app.update()
    try:
        assert "A real test subject line" in _all_label_text(dlg)
    finally:
        dlg.destroy()


def test_send_confirmation_dialog_without_subject_omits_subject_row(app):
    from src.ui.send_dialogs import SendConfirmationDialog

    dlg = SendConfirmationDialog(
        app, "whatsapp", 3, 10.0, ["To: 1\nHi"], on_confirm=lambda: None)
    app.update()
    try:
        assert "Subject" not in _all_label_text(dlg)
    finally:
        dlg.destroy()

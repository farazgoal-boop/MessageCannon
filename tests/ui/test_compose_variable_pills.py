"""Item 9 of the Live Testing Findings pass: replace raw {name}/{amount}-style
variable text in Compose with a clean "Insert variable ▾" dropdown that
inserts a subtle pill/chip (matching the app's existing metadata-pill style,
e.g. "30 sec cadence") instead of showing raw braces — a display/insertion
UX change only; the underlying stored/sent text is still the literal
{token} string.

Real bug found while building this, via direct reproduction (not assumed):
Tk's `Text.get()` silently *omits* embedded windows from its returned string
entirely (no placeholder character at all), so a naive "get the whole text,
regex over that string, convert string offsets straight into Tk indices"
approach for `_pillify_text_widget` drifted out of alignment by one real Tk
index per pill already in the buffer, corrupting whatever followed the first
pill (typing "{amount}" right after an already-pillified {name} deleted the
wrong characters and left a stray brace behind). Fixed by working from
`.dump(text=True)`'s own per-segment real starting index instead of a single
global string offset — see `_pillify_text_widget`'s own docstring in
main_window.py for the full account.
"""

from __future__ import annotations

import customtkinter as ctk

from src.models import Contact


def _reset_wa_editor(app):
    app.message_textbox.delete("1.0", "end")
    app._on_wa_message_changed()
    app.update()


def _reset_em_editor(app, original_body: str):
    app._compose_em_body.delete("1.0", "end")
    app._compose_em_body.insert("1.0", original_body)
    app._update_email_warnings()
    app.update()


def _pill_labels_and_tokens(text_widget):
    inner = getattr(text_widget, "_textbox", text_widget)
    out = []
    for key, value, _index in inner.dump("1.0", "end", window=True):
        if key == "window" and value:
            widget = inner.nametowidget(value)
            out.append((widget.cget("text"), widget.var_token))
    return out


def test_wa_dropdown_inserts_pill_not_raw_braces(app):
    _reset_wa_editor(app)
    try:
        app.wa_insert_variable_menu._command("Name")
        app.update()

        assert app._get_text_with_tokens(app.message_textbox) == "{name}\n"
        # The raw braces must not be visible as literal text in the widget --
        # only reconstructible via _get_text_with_tokens.
        raw = app.message_textbox._textbox.get("1.0", "end")
        assert "{name}" not in raw
        pills = _pill_labels_and_tokens(app.message_textbox)
        assert pills == [("Name", "{name}")]
    finally:
        _reset_wa_editor(app)


def test_wa_dropdown_resets_to_placeholder_after_pick(app):
    _reset_wa_editor(app)
    try:
        placeholder = app.wa_insert_variable_menu.get()
        assert "Insert variable" in placeholder
        app.wa_insert_variable_menu._command("Amount")
        app.update()
        assert app.wa_insert_variable_menu.get() == placeholder, (
            "the menu is a command menu, not a persistent selector -- it must "
            "not get stuck showing the last-picked label")
    finally:
        _reset_wa_editor(app)


def test_manually_typed_raw_token_after_an_existing_pill_still_pillifies_correctly(app):
    """The literal repro of the real bug found this pass: typing more raw
    {token} text right after an already-pillified variable must not corrupt
    the surrounding text."""
    _reset_wa_editor(app)
    try:
        app.wa_insert_variable_menu._command("Name")
        app.update()
        app.message_textbox.insert("insert", " costs {amount} due {date}")
        app._on_wa_message_changed()
        app.update()

        assert app._get_text_with_tokens(app.message_textbox) == (
            "{name} costs {amount} due {date}\n")
        pills = _pill_labels_and_tokens(app.message_textbox)
        assert pills == [("Name", "{name}"), ("Amount", "{amount}"), ("Date", "{date}")]
    finally:
        _reset_wa_editor(app)


def test_em_dropdown_inserts_pill_and_resets_placeholder(app):
    original_body = app._compose_em_body.get("1.0", "end")
    try:
        app._compose_em_body.delete("1.0", "end")
        app._update_email_warnings()
        app.update()

        placeholder = app.em_insert_variable_menu.get()
        app.em_insert_variable_menu._command("Email")
        app.update()

        assert app._get_text_with_tokens(app._compose_em_body) == "{email}\n"
        assert app.em_insert_variable_menu.get() == placeholder
        raw = app._compose_em_body.get("1.0", "end")
        assert "{email}" not in raw
    finally:
        _reset_em_editor(app, original_body)


def test_preview_substitutes_correctly_from_pillified_message(app):
    """_refresh_preview must read the real {name} token back out from the
    pill, not a placeholder character -- otherwise the personalized preview
    (and, by the same code path, the actual outgoing send) would be wrong."""
    original_contacts = app.contacts
    original_vars = dict(app.contact_selection_vars)
    _reset_wa_editor(app)
    try:
        app.contacts = [Contact(id=9301, phone="+15550009301", email="", name="Priya")]
        app._sync_contact_selection()
        app._render_compose_contacts()
        for var in app.contact_selection_vars.values():
            var.set(True)

        app.wa_insert_variable_menu._command("Name")
        app.update()
        app.message_textbox.insert("insert", ", welcome!")
        app._on_wa_message_changed()
        app.update()

        preview = app.preview_text.get("1.0", "end")
        assert "Priya, welcome!" in preview
        assert "{name}" not in preview
    finally:
        app.contacts = original_contacts
        app.contact_selection_vars = original_vars
        app._render_compose_contacts()
        app._update_compose_summary()
        _reset_wa_editor(app)


def test_char_count_warning_reflects_real_token_length_not_placeholder(app):
    """_update_wa_warning must count the real {phone} token's length, not a
    1-character placeholder, or the WhatsApp length warning would silently
    under-count messages using pilled variables."""
    _reset_wa_editor(app)
    try:
        app.message_textbox.insert("1.0", "Contact: ")
        app._on_wa_message_changed()
        app.wa_insert_variable_menu._command("Phone")
        app.update()

        expected_len = len("Contact: {phone}\n".strip())
        assert app._wa_warning_var.get() == f"{expected_len} characters"
    finally:
        _reset_wa_editor(app)


def test_loading_a_real_email_template_with_multiple_unlisted_tokens_roundtrips(app):
    """EMAIL_TEMPLATES' "Invoice" entry uses {invoice_no}/{sender} on top of
    the common {name}/{amount}/{date} -- tokens outside _VARIABLE_TOKEN_LABELS'
    known set, so this also exercises _label_for_variable_token's derived-
    label fallback (e.g. "{invoice_no}" -> "Invoice No")."""
    import src.ui.main_window as mw_mod

    original_body = app._compose_em_body.get("1.0", "end")
    try:
        _, html, _is_html = mw_mod.EMAIL_TEMPLATES["Invoice"]
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", html)
        app._update_email_warnings()
        app.update()

        assert app._get_text_with_tokens(app._compose_em_body).strip() == html.strip()
        tokens = {token for _label, token in _pill_labels_and_tokens(app._compose_em_body)}
        assert tokens == {"{name}", "{amount}", "{date}", "{invoice_no}", "{sender}"}
    finally:
        _reset_em_editor(app, original_body)


def test_save_template_reads_canonical_text_not_placeholder_chars(app):
    _reset_wa_editor(app)
    try:
        app.wa_insert_variable_menu._command("Name")
        app.update()
        app.message_textbox.insert("insert", " your order {amount} ships {date}")
        app._on_wa_message_changed()
        app.update()

        text = app._get_text_with_tokens(app.message_textbox).strip()
        assert text == "{name} your order {amount} ships {date}"
    finally:
        _reset_wa_editor(app)

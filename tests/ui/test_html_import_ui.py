"""Item 33 of the multi-product generalization pass: real "Import HTML
Card/Page" feature, driven end to end through the real UI entry points --
Card Creator's own "📂 Import HTML File" button and Compose's own
"📂 Import HTML" button -- both routing into the same real send pipelines
proven elsewhere in this suite (CardCreatorV2._insert_into_compose,
MainWindow._enter_email_card_mode).
"""

from __future__ import annotations


def _write_card_html(tmp_path, name="external_card.html", with_script=True):
    script = '<script>alert("x")</script>' if with_script else ""
    path = tmp_path / name
    path.write_text(
        f'<html><head><title>Imported Deal</title>{script}</head>'
        '<body><h1>Big Sale</h1><p>Hi {name}, get {amount} off.</p>'
        '<a href="https://example.com/buy">Buy Now</a></body></html>'
    )
    return str(path)


def test_card_creator_import_html_file_end_to_end(app, tmp_path, monkeypatch):
    """Drives the real button's own method: file dialog mocked to return a
    real temp HTML file (containing a <script> tag, to prove sanitization
    genuinely ran), everything else is the real import path."""
    tab = app.card_creator_tab
    path = _write_card_html(tmp_path)
    monkeypatch.setattr(
        "src.ui.card_creator_tab.filedialog.askopenfilename", lambda **k: path)
    try:
        tab._import_html_file()
        app.update()

        assert tab._imported_html_active is True
        assert "<script" not in tab._html
        assert "alert" not in tab._html
        assert "{name}" in tab._html and "{amount}" in tab._html
        assert tab._imported_html_subject == "Imported Deal"
        assert tab._imported_html_status.get() != ""
    finally:
        tab._imported_html_active = False
        tab._load_preset("SaaS Product")
        app.update()


def test_editing_a_field_after_import_exits_imported_mode(app, tmp_path, monkeypatch):
    """Item 33's own documented behavior: any further edit after an import
    means the user wants the section-based builder back."""
    tab = app.card_creator_tab
    path = _write_card_html(tmp_path)
    monkeypatch.setattr(
        "src.ui.card_creator_tab.filedialog.askopenfilename", lambda **k: path)
    try:
        tab._import_html_file()
        app.update()
        assert tab._imported_html_active is True

        tab._mtag.set("edited after import")
        app.update()

        assert tab._imported_html_active is False
        assert tab._imported_html_status.get() == ""
    finally:
        tab._imported_html_active = False
        tab._load_preset("SaaS Product")
        app.update()


def test_import_html_rejects_a_bad_file_with_a_clear_message(app, tmp_path, monkeypatch):
    bad_path = tmp_path / "notes.txt"
    bad_path.write_text("not html")
    monkeypatch.setattr(
        "src.ui.card_creator_tab.filedialog.askopenfilename", lambda **k: str(bad_path))
    shown = {}

    def fake_showerror(title, message):
        shown["title"] = title
        shown["message"] = message

    monkeypatch.setattr("src.ui.card_creator_tab.messagebox.showerror", fake_showerror)
    tab = app.card_creator_tab
    tab._imported_html_active = False
    tab._import_html_file()
    app.update()

    assert shown.get("title") == "Import failed"
    assert "doesn't look like" in shown.get("message", "")
    assert tab._imported_html_active is False


def test_insert_into_compose_email_from_import_uses_visual_card_mode(app, tmp_path, monkeypatch):
    """Item 33 ask #5: an imported card flows into Compose exactly like the
    real "Send as Visual HTML Card" mode -- real HTML sent as-is, not
    flattened -- with no rich-text-vs-card choice dialog (that choice only
    makes sense for a Card-Creator-generated card)."""
    tab = app.card_creator_tab
    path = _write_card_html(tmp_path)
    monkeypatch.setattr(
        "src.ui.card_creator_tab.filedialog.askopenfilename", lambda **k: path)
    original_channel = app._compose_channel_var.get()
    try:
        tab._import_html_file()
        app.update()

        app._compose_channel_var.set("Email")
        tab._insert_into_compose()
        app.update()

        assert app._compose_card_mode is True
        assert "<script" not in app._compose_card_html_template
        assert "{name}" in app._compose_card_html_template
        assert app._em_subj_var.get() == "Imported Deal"
    finally:
        app._exit_email_card_mode()
        app._compose_channel_var.set(original_channel)
        tab._imported_html_active = False
        tab._load_preset("SaaS Product")
        app.update()


def test_insert_into_compose_whatsapp_from_import_flattens_to_plain_text(app, tmp_path, monkeypatch):
    tab = app.card_creator_tab
    path = _write_card_html(tmp_path)
    monkeypatch.setattr(
        "src.ui.card_creator_tab.filedialog.askopenfilename", lambda **k: path)
    original_channel = app._compose_channel_var.get()
    try:
        tab._import_html_file()
        app.update()

        app._compose_channel_var.set("WhatsApp")
        tab._insert_into_compose()
        app.update()

        text = app.message_textbox.get("1.0", "end")
        assert "<h1>" not in text and "<p>" not in text
        assert "Big Sale" in text
        assert "https://example.com/buy" in text
    finally:
        app._compose_channel_var.set(original_channel)
        tab._imported_html_active = False
        tab._load_preset("SaaS Product")
        app.update()


def test_compose_direct_import_html_button_enters_visual_card_mode(app, tmp_path, monkeypatch):
    """The second real entry point (ask #1's "and/or directly in Compose's
    Email mode"): MainWindow._import_html_into_compose, wired to the real
    "📂 Import HTML" button next to Compose's own Save-as-Template button."""
    path = _write_card_html(tmp_path, name="direct_compose_import.html")
    monkeypatch.setattr(
        "src.ui.main_window.filedialog.askopenfilename", lambda **k: path)
    try:
        app._import_html_into_compose()
        app.update()

        assert app._compose_card_mode is True
        assert "<script" not in app._compose_card_html_template
        assert "{amount}" in app._compose_card_html_template
        assert app._em_subj_var.get() == "Imported Deal"
    finally:
        app._exit_email_card_mode()
        app.update()


def test_import_html_button_is_a_real_findable_widget_in_compose(app):
    assert hasattr(app, "_em_import_html_btn")
    assert app._em_import_html_btn.winfo_exists()
    assert app._em_import_html_btn.cget("text") == "📂 Import HTML"

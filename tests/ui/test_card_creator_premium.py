"""Item 11 of the Live Testing Findings pass (Round 2): Card Creator rebuild
-- making it genuinely visual, AI-driven, and conversion-ready.

Studied the existing implementation fully before writing any code, per this
file's own standing "study before building" discipline. Several of the
item's 6 asks turned out to already exist from an earlier pass (the "Final
Completion Pass" section of CLAUDE.md) -- notably (2), AI suggesting a
matching style/color and drafting feature bullets, which `generate_card_copy`
and `_apply_ai_card_copy` already implement. This file adds real, direct test
coverage for that path (previously only ever verified by reading the code,
never by a real widget-level test), plus coverage for every genuinely new
piece built this pass.

Real, pre-existing bug found while studying this file for this item (not
part of any single numbered sub-item, but too real to leave unflagged):
`main_window.py`'s own `_sync_widget_theme` reads
`getattr(self, "card_creator_tab", None)` to re-color the Cards preview
host's raw `tk.Frame` background on every theme toggle -- but
`build_card_creator_view` never actually assigned that attribute anywhere,
so the whole block was silently always a no-op (the Cards preview
background never re-themed). Fixed by assigning
`main_window.card_creator_tab = tab` at the end of `build_card_creator_view`.
"""

from __future__ import annotations

import customtkinter as ctk

import src.ui.theme as T


def test_card_creator_tab_attribute_is_wired_on_main_window(app):
    """The literal repro of the real bug found while studying this file:
    main_window.card_creator_tab must be the real, live CardCreatorV2
    instance, not missing/None."""
    assert getattr(app, "card_creator_tab", None) is not None
    assert app.card_creator_tab.__class__.__name__ == "CardCreatorV2"


def test_cards_preview_host_background_actually_retheme(app):
    """Confirms the fix is load-bearing, not just present: the preview
    host's real bg color changes across a theme toggle."""
    original_theme = app.theme_var.get()
    try:
        app._on_theme_selected("Dark")
        app.update()
        app._sync_theme_overrides()
        dark_bg = app.card_creator_tab._preview_host.cget("bg")

        app._on_theme_selected("Light")
        app.update()
        app._sync_theme_overrides()
        light_bg = app.card_creator_tab._preview_host.cget("bg")

        assert dark_bg != light_bg, (
            "Cards preview host background did not change across a real "
            "Dark->Light toggle -- the card_creator_tab wiring regressed")
    finally:
        app._on_theme_selected(original_theme)
        app.update()


def test_ai_card_copy_sets_matching_accent_from_style_name(app):
    """Item 11.2: "AI should suggest a matching theme/color... not just body
    copy" -- confirms _apply_ai_card_copy really does set self._accent from
    the AI-picked style_name (already built in an earlier pass; this is its
    first direct widget-level test)."""
    tab = app.card_creator_tab
    original_accent = tab._accent
    original_template = tab._template_var.get()
    try:
        tab._apply_ai_card_copy({
            "icon": "🚀", "tagline": "Ship Faster", "description": "A great tool.",
            "features": ["Fast", "Reliable", "Simple"],
            "price": "$19", "old_price": "$29", "price_note": "Monthly",
            "style_name": "Green Tech",
        })
        assert tab._template_var.get() == "Green Tech"
        from src.ui.card_creator_tab import CARD_STYLE_TEMPLATES
        assert tab._accent == CARD_STYLE_TEMPLATES["Green Tech"]["accent"]
    finally:
        tab._accent = original_accent
        tab._template_var.set(original_template)


def test_ai_card_copy_drafts_feature_bullets_not_just_body_copy(app):
    """The other half of Item 11.2 -- feature bullets, not just description
    text, actually flow into the Features section's textbox."""
    tab = app.card_creator_tab
    try:
        tab._apply_ai_card_copy({
            "icon": "🚀", "tagline": "Ship Faster", "description": "A great tool.",
            "features": ["Real-time sync", "Offline mode", "Team collaboration"],
            "price": "", "old_price": "", "price_note": "", "style_name": "Dark Premium",
        })
        features_box = next(
            (s["data"].get("_box") for s in tab._sections if s["type"] == "features"), None)
        assert features_box is not None
        text = features_box.get("1.0", "end")
        assert "Real-time sync" in text
        assert "Offline mode" in text
        assert "Team collaboration" in text
    finally:
        tab._load_preset("MessageCannon Pro")


def _price_section(tab):
    return next(s for s in tab._sections if s["type"] == "price")


def test_price_section_has_button_text_and_buy_url_fields_defaulting_correctly(app):
    """Item 11.5: real fields on the Price section itself, Button Text
    defaulting to "Buy Now" as explicitly requested."""
    tab = app.card_creator_tab
    sec = _price_section(tab)
    assert sec["data"]["_btn_text"].get() == "Buy Now"
    assert sec["data"]["_buy_url"].get() == ""


def test_price_section_collects_button_text_url_and_discount_percent(app):
    tab = app.card_creator_tab
    sec = _price_section(tab)
    try:
        sec["data"]["_price"].set("$69")
        sec["data"]["_old"].set("$100")
        sec["data"]["_btn_text"].set("Grab This Deal")
        sec["data"]["_buy_url"].set("https://mystore.com/buy")
        app.update()

        collected = tab._collect_sections()
        price_data = next(d["data"] for d in collected if d["type"] == "price")
        assert price_data["button_text"] == "Grab This Deal"
        assert price_data["buy_url"] == "https://mystore.com/buy"
        assert price_data["discount_percent"] == 31
    finally:
        sec["data"]["_price"].set("$89")
        sec["data"]["_old"].set("$129")
        sec["data"]["_btn_text"].set("Buy Now")
        sec["data"]["_buy_url"].set("")


def test_price_section_end_to_end_html_has_real_clickable_buy_button(app):
    """Proof required by Item 11: a full sample card with a working buy
    button, generated end-to-end through the real widget (not a hand-built
    sections dict)."""
    tab = app.card_creator_tab
    sec = _price_section(tab)
    original = {k: sec["data"][k].get() for k in ("_price", "_old", "_btn_text", "_buy_url")}
    try:
        sec["data"]["_price"].set("$49")
        sec["data"]["_old"].set("$99")
        sec["data"]["_btn_text"].set("Get MessageCannon Pro")
        sec["data"]["_buy_url"].set("https://example.com/checkout")
        app.update()

        html = tab._get_export_html()
        assert 'href="https://example.com/checkout"' in html
        assert "Get MessageCannon Pro →" in html
        assert "51% OFF" in html
    finally:
        for key, value in original.items():
            sec["data"][key].set(value)


def test_accent_swatches_are_real_pixel_sized_canvases_not_tiny_buttons(app):
    """Item 11.3: "larger visual swatches" -- confirms the swatches are
    real ~30px canvases (the old implementation used a 2-character-wide
    tk.Button, which renders far smaller)."""
    import tkinter as tk
    tab = app.card_creator_tab
    assert tab._accent_swatch_canvases, "expected at least one accent swatch"
    for canvas in tab._accent_swatch_canvases.values():
        assert isinstance(canvas, tk.Canvas)
        assert int(canvas.cget("width")) >= 28
        assert int(canvas.cget("height")) >= 28


def test_selecting_an_accent_swatch_updates_accent_and_selection_ring(app):
    from src.ui.card_creator_tab import ACCENT_COLORS
    tab = app.card_creator_tab
    original_accent = tab._accent
    try:
        target = ACCENT_COLORS[1]
        tab._select_accent(target)
        app.update()
        assert tab._accent == target

        # The selected swatch's canvas should have a thicker (selected)
        # border than an unselected one.
        selected_canvas = tab._accent_swatch_canvases[target]
        other_canvas = tab._accent_swatch_canvases[ACCENT_COLORS[0]]

        def border_width(canvas):
            for item in canvas.find_all():
                if canvas.type(item) == "rectangle" and canvas.itemcget(item, "fill") == "":
                    return int(float(canvas.itemcget(item, "width")))
            return None

        assert border_width(selected_canvas) == 3
        assert border_width(other_canvas) == 1
    finally:
        tab._select_accent(original_accent)


def test_template_gallery_has_a_thumbnail_per_template_plus_custom(app):
    from src.ui.card_creator_tab import CARD_STYLE_TEMPLATES
    tab = app.card_creator_tab
    expected_names = set(CARD_STYLE_TEMPLATES.keys()) | {"Custom"}
    assert set(tab._template_thumb_canvases.keys()) == expected_names
    for canvas in tab._template_thumb_canvases.values():
        assert int(canvas.cget("width")) >= 80


def test_selecting_a_template_thumbnail_applies_style_and_highlights_it(app):
    tab = app.card_creator_tab
    original_template = tab._template_var.get()
    try:
        tab._select_template("Green Tech")
        app.update()
        assert tab._template_var.get() == "Green Tech"
        assert tab._style_name == "Green Tech"
        from src.ui.card_creator_tab import CARD_STYLE_TEMPLATES
        assert tab._accent == CARD_STYLE_TEMPLATES["Green Tech"]["accent"]
        # Item 27 of the Final Premium Polish Pass: this label's selected-state
        # text_color is T.ACCENT_TEXT, not plain T.ACCENT -- plain ACCENT
        # measured a real WCAG contrast fail (2.61:1) against this label's
        # T.BG_SURFACE-toned parent in Dark mode; ACCENT_TEXT passes AA.
        assert tab._template_thumb_labels["Green Tech"].cget("text_color") == T.ACCENT_TEXT
        assert tab._template_thumb_labels[original_template if original_template != "Green Tech"
                                           else "Dark Premium"].cget("text_color") != T.ACCENT_TEXT
    finally:
        tab._select_template(original_template)


def test_custom_template_thumbnail_reflects_custom_background_color(app):
    """The gallery's "Custom" thumbnail must actually redraw when the user
    picks a custom background color -- exercises _redraw_template_gallery
    being called from _pick_custom_bg_color's real code path (simulated
    here without a real color-picker dialog)."""
    tab = app.card_creator_tab
    original_style = dict(tab._custom_style)
    try:
        tab._custom_style.update({
            "bg": "#112233", "body_bg": "#112233", "header_bg": "#112233",
            "text": "rgba(255,255,255,0.85)",
        })
        tab._redraw_template_gallery()
        app.update()
        canvas = tab._template_thumb_canvases["Custom"]
        fills = {canvas.itemcget(item, "fill") for item in canvas.find_all()
                 if canvas.type(item) == "rectangle"}
        assert "#112233" in fills
    finally:
        tab._custom_style.clear()
        tab._custom_style.update(original_style)
        tab._redraw_template_gallery()


def test_custom_bg_image_is_not_embedded_twice(app, tmp_path, monkeypatch):
    """Item 23 of the Live Testing Findings pass (Round 2): a real bug
    found by direct measurement -- _pick_custom_bg_image used to set BOTH
    "bg" (.card's own background) and "body_bg" (the full-page backdrop,
    only ever visible as a thin margin around the card) to the exact same
    image url(...) value, embedding the same base64 payload twice in the
    exported HTML for no visual benefit. Drives the real button's own
    method end-to-end (file dialog mocked to return a real temp PNG, the
    rest of the flow is genuine)."""
    tab = app.card_creator_tab
    original_style = dict(tab._custom_style)
    original_style_name = tab._style_name
    original_icon_uri = tab._micon_image_uri
    tab._micon_image_uri = None  # isolate from any other test's icon upload state
    try:
        tab._select_template("Custom")  # _collect_meta only reads _custom_style when this is active
        path = _write_tiny_png(tmp_path)
        monkeypatch.setattr(
            "src.ui.card_creator_tab.filedialog.askopenfilename", lambda **k: path)

        tab._pick_custom_bg_image()
        app.update()

        assert tab._custom_style["bg"].startswith("url(data:image/png;base64,")
        assert tab._custom_style["body_bg"] == "#1a1a2e"

        html = tab._get_export_html()
        assert html.count("base64,") == 1, (
            "the same image payload must only be embedded once in the exported card")
    finally:
        tab._custom_style.clear()
        tab._custom_style.update(original_style)
        tab._micon_image_uri = original_icon_uri
        tab._select_template(original_style_name)
        tab._redraw_template_gallery()
        tab._schedule_preview()


def _write_tiny_png(tmp_path) -> str:
    import base64
    # Same known-valid 1x1 transparent PNG already used in
    # tests/test_card_generator.py's own image-upload tests.
    tiny_png = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "+A8AAQUBAScY42YAAAAASUVORK5CYII="
    )
    path = tmp_path / "logo.png"
    path.write_bytes(tiny_png)
    return str(path)


def test_icon_drop_zone_defaults_to_no_image_and_emoji_fallback(app):
    tab = app.card_creator_tab
    assert tab._micon_image_uri is None
    assert tab._icon_crop_btn.cget("state") == "disabled"


def _canvas_dash_items(canvas):
    return [item for item in canvas.find_all()
            if canvas.type(item) == "rectangle" and canvas.itemcget(item, "dash")]


def test_icon_zone_is_a_real_sized_drop_zone_not_a_tiny_icon(app):
    """Item 20: the drop zone must be a genuine, roomy zone (was a plain
    44x44 canvas before), and must show a real dashed border plus explicit
    drag-and-drop helper text in its empty state, not just a tiny emoji."""
    tab = app.card_creator_tab
    canvas = tab._icon_preview_canvas
    assert int(canvas.cget("width")) >= 100
    assert int(canvas.cget("height")) >= 80

    assert tab._micon_image_uri is None  # confirm we're testing the empty state
    dashed = _canvas_dash_items(canvas)
    assert dashed, "expected a real dashed-border rectangle in the empty state"

    texts = [canvas.itemcget(item, "text") for item in canvas.find_all()
             if canvas.type(item) == "text"]
    combined = " ".join(texts)
    assert "Drag & drop" in combined
    assert "click to browse" in combined


def test_icon_zone_helper_text_does_not_clip_at_canvas_edges(app):
    """Item 25: the empty-state helper text ("Drag & drop logo here, or
    click to browse") was reported cut off on the left ("g & drop logo
    he..."). Root cause: the canvas text item had no `width=`, so it never
    word-wrapped -- the longest line alone measures wider than the 128px
    zone, and being center-anchored, roughly half of it rendered at a
    negative x-coordinate and was clipped by the canvas viewport. Asserts
    the real rendered bbox of the text item stays fully inside the
    canvas's own [0, width] bounds -- this must fail against the pre-fix
    code (no `width=` argument) and pass now that wrapping is forced."""
    tab = app.card_creator_tab
    canvas = tab._icon_preview_canvas
    assert tab._micon_image_uri is None  # confirm testing the empty state

    text_items = [item for item in canvas.find_all() if canvas.type(item) == "text"]
    assert text_items, "expected a real text item in the empty state"
    zone_width = int(canvas.cget("width"))
    for item in text_items:
        x0, _y0, x1, _y1 = canvas.bbox(item)
        assert x0 >= 0, f"text clipped on the left: bbox starts at {x0}"
        assert x1 <= zone_width, f"text clipped on the right: bbox ends at {x1} (zone width {zone_width})"


def test_icon_zone_hover_changes_border_and_background(app):
    """Item 20: real hover feedback -- a plain tk.Canvas has no CSS :hover,
    so this is hand-painted on <Enter>/<Leave>, confirmed by checking the
    actual rendered colors change, not just that the bindings exist."""
    tab = app.card_creator_tab
    canvas = tab._icon_preview_canvas
    try:
        tab._set_icon_zone_hover(False)
        bg_normal = canvas.cget("bg")
        dashed_normal = _canvas_dash_items(canvas)
        border_normal = canvas.itemcget(dashed_normal[0], "outline") if dashed_normal else None

        tab._set_icon_zone_hover(True)
        bg_hover = canvas.cget("bg")
        dashed_hover = _canvas_dash_items(canvas)
        border_hover = canvas.itemcget(dashed_hover[0], "outline") if dashed_hover else None

        assert bg_hover != bg_normal, "canvas background did not change on hover"
        assert border_hover != border_normal, "border color did not change on hover"
    finally:
        tab._set_icon_zone_hover(False)


def test_icon_zone_shows_properly_sized_thumbnail_not_tiny_icon_once_uploaded(app, tmp_path):
    """Item 20: once an image is uploaded, the zone must show a real,
    properly-sized thumbnail (filling most of the zone) instead of the old
    tiny 42x42-max icon rendering -- and the dashed empty-state border/
    helper text must be gone."""
    tab = app.card_creator_tab
    try:
        path = _write_tiny_png(tmp_path)
        tab._load_icon_image_path(path)
        app.update()

        canvas = tab._icon_preview_canvas
        images = [item for item in canvas.find_all() if canvas.type(item) == "image"]
        assert images, "expected a real embedded thumbnail image on the canvas"
        assert not _canvas_dash_items(canvas), (
            "dashed empty-state border should be gone once an image is uploaded")
        texts = [canvas.itemcget(item, "text") for item in canvas.find_all()
                 if canvas.type(item) == "text"]
        assert not any("Drag & drop" in t for t in texts)
    finally:
        tab._clear_icon_image()


def test_loading_a_real_icon_image_updates_state_and_enables_crop(app, tmp_path):
    tab = app.card_creator_tab
    try:
        path = _write_tiny_png(tmp_path)
        tab._load_icon_image_path(path)
        app.update()

        assert tab._micon_image_uri is not None
        assert tab._micon_image_uri.startswith("data:image/png;base64,")
        assert tab._icon_crop_btn.cget("state") == "normal"
    finally:
        tab._clear_icon_image()


def test_clearing_icon_image_reverts_to_emoji_fallback(app, tmp_path):
    tab = app.card_creator_tab
    try:
        path = _write_tiny_png(tmp_path)
        tab._load_icon_image_path(path)
        app.update()
        assert tab._micon_image_uri is not None

        tab._clear_icon_image()
        app.update()
        assert tab._micon_image_uri is None
        assert tab._icon_crop_btn.cget("state") == "disabled"
    finally:
        tab._clear_icon_image()


def test_uploaded_icon_renders_as_real_img_tag_in_exported_card(app, tmp_path):
    """Proof required by Item 11: end-to-end through the real widget, not
    a hand-built sections dict."""
    tab = app.card_creator_tab
    try:
        path = _write_tiny_png(tmp_path)
        tab._load_icon_image_path(path)
        app.update()

        html = tab._get_export_html()
        assert f'<img src="{tab._micon_image_uri}"' in html
    finally:
        tab._clear_icon_image()


def test_crop_dialog_is_a_noop_without_an_uploaded_image(app):
    tab = app.card_creator_tab
    before_toplevels = [w for w in tab.winfo_children() if w.winfo_class() == "Toplevel"]
    tab._open_icon_crop_dialog()
    app.update()
    after_toplevels = [w for w in tab.winfo_children() if w.winfo_class() == "Toplevel"]
    assert len(after_toplevels) == len(before_toplevels), (
        "crop dialog must not open when there is no uploaded image to crop")


def test_crop_dialog_opens_with_real_image_and_cancels_cleanly(app, tmp_path):
    tab = app.card_creator_tab
    try:
        path = _write_tiny_png(tmp_path)
        tab._load_icon_image_path(path)
        app.update()

        tab._open_icon_crop_dialog()
        app.update()
        dialogs = [w for w in tab.winfo_children()
                   if w.winfo_class() == "Toplevel" and w.title() == "Crop Logo"]
        assert len(dialogs) == 1
        dialogs[0].destroy()
        app.update()
    finally:
        tab._clear_icon_image()


def test_build_whatsapp_card_text_includes_headline_price_discount_and_link(app):
    """Item 11.6: WhatsApp can't render HTML, so the card's key selling
    points must flatten into real plain text -- headline, description,
    price/discount, and a working purchase link."""
    tab = app.card_creator_tab
    sec = _price_section(tab)
    original = {k: sec["data"][k].get() for k in ("_price", "_old", "_btn_text", "_buy_url")}
    try:
        sec["data"]["_price"].set("$49")
        sec["data"]["_old"].set("$99")
        sec["data"]["_btn_text"].set("Get It Now")
        sec["data"]["_buy_url"].set("https://example.com/checkout")

        meta = tab._collect_meta()
        text = tab._build_whatsapp_card_text(meta)

        assert meta["app_name"] in text
        assert "$49" in text and "$99" in text
        assert "51% OFF" in text
        assert "Get It Now: https://example.com/checkout" in text
    finally:
        for key, value in original.items():
            sec["data"][key].set(value)


def test_insert_into_compose_email_loads_html_into_rich_editor(app):
    """Proof required by Item 11: end-to-end insert into the real Compose
    Email editor, reusing Item 10's HTML importer so the card lands as
    genuine editable/sendable content."""
    tab = app.card_creator_tab
    original_channel = app._compose_channel_var.get()
    original_subject = app._em_subj_var.get()
    original_body = app._compose_em_body.get("1.0", "end")
    original_view = app._active_view
    try:
        app._compose_channel_var.set("Email")
        app._on_channel_switch("Email")
        app.update()

        tab._insert_into_compose()
        app.update()

        assert app._active_view == "Compose"
        raw_body = app._compose_em_body.get("1.0", "end")
        assert "<" not in raw_body  # the importer must strip raw tags, same as Item 10
        meta = tab._collect_meta()
        assert meta["app_name"] in raw_body or meta["app_name"] in app._em_subj_var.get()
        assert app._em_subj_var.get().strip() != ""
    finally:
        app._compose_channel_var.set(original_channel)
        app._on_channel_switch(original_channel)
        app._em_subj_var.set(original_subject)
        app._compose_em_body.delete("1.0", "end")
        app._compose_em_body.insert("1.0", original_body)
        app._update_email_warnings()
        app._show_view(original_view)
        app.update()


def test_insert_into_compose_whatsapp_loads_plain_text_summary(app):
    tab = app.card_creator_tab
    original_channel = app._compose_channel_var.get()
    original_wa_text = app._get_text_with_tokens(app.message_textbox)
    original_view = app._active_view
    try:
        app._compose_channel_var.set("WhatsApp")
        app._on_channel_switch("WhatsApp")
        app.update()

        tab._insert_into_compose()
        app.update()

        assert app._active_view == "Compose"
        wa_text = app._get_text_with_tokens(app.message_textbox)
        meta = tab._collect_meta()
        assert meta["app_name"] in wa_text
        assert "<" not in wa_text
    finally:
        app._compose_channel_var.set(original_channel)
        app._on_channel_switch(original_channel)
        app.message_textbox.delete("1.0", "end")
        app.message_textbox.insert("1.0", original_wa_text)
        app._on_wa_message_changed()
        app._show_view(original_view)
        app.update()


def test_card_identity_panel_is_a_real_scrollable_frame(app):
    """Item 18 of the Live Testing Findings pass (Round 2): the Card
    Identity panel must be a real CTkScrollableFrame, not a plain frame
    that just grows to its full content height with nothing to scroll it."""
    tab = app.card_creator_tab
    assert isinstance(tab._card_identity_panel, ctk.CTkScrollableFrame)


def test_card_identity_panel_and_sections_list_both_get_bounded_real_height(app):
    """A sanity check that both regions get a real, non-trivial share of
    height under a deliberately shrunk window (1220x420, the same
    window-shrink technique test_setup_wizard_layout.py already uses).
    Note on what this test does and doesn't prove: attempts to force this
    same assertion to fail against the pre-fix code (plain CTkFrame, no row
    weight) did NOT reproduce a sub-50px squeeze even at this shrunk size in
    this harness -- Tk's grid geometry manager apparently still gave the
    sections list a usable minimum here. The real, unambiguous proof that
    the fix is meaningful is test_card_identity_panel_is_a_real_scrollable_
    frame: a plain CTkFrame provides no scroll capability at all regardless
    of how the squeeze plays out, so confirming the panel is now a real
    CTkScrollableFrame is what actually guarantees overflow content stays
    reachable -- this test is a supporting sanity check, not the primary
    evidence."""
    original_geometry = app.geometry()
    try:
        app._show_view("Cards")
        app.update()
        tab = app.card_creator_tab
        if not tab._sections_advanced_expanded:
            tab._toggle_advanced_sections()
        app.geometry("1220x420")
        app.update()

        identity_height = tab._card_identity_panel.winfo_height()
        sections_height = tab._sections_scroll.winfo_height()

        assert identity_height > 50, f"Card Identity panel height was {identity_height}px"
        assert sections_height > 50, (
            f"Sections list (where the Item 11.5 price fields live) height was "
            f"{sections_height}px -- squeezed to near-zero by an unbounded Card "
            f"Identity panel above it")
    finally:
        app.geometry(original_geometry)
        if tab._sections_advanced_expanded:
            tab._toggle_advanced_sections()
        app.update()


def test_price_section_fields_are_reachable_inside_the_sections_scroll(app):
    """Confirms the Button Text/Purchase Link URL fields from Item 11.5 --
    specifically named as unreachable in the report -- are real descendants
    of the sections list's own scrollable frame, which the fix above
    restores real height to."""
    tab = app.card_creator_tab
    sec = _price_section(tab)
    buy_url_var = sec["data"]["_buy_url"]
    # The StringVar itself has no winfo_* methods -- walk to find the real
    # entry widget bound to it instead (CTkEntry keeps the real variable
    # object on ._textvariable, compared by identity), confirming it's a
    # mapped descendant of _sections_scroll (not orphaned or hidden).
    found = False

    def walk(widget):
        nonlocal found
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkEntry) and getattr(child, "_textvariable", None) is buy_url_var:
                found = True
                return
            walk(child)

    walk(tab._sections_scroll)
    assert found, "Purchase Link URL entry not found as a real descendant of the sections scroll area"


def test_card_is_clean_right_after_loading_a_preset(app):
    """Item 17: _load_preset's own internal section-building must not
    itself count as "dirty" content -- otherwise every preset switch would
    always look dirty and nag on every single click."""
    tab = app.card_creator_tab
    try:
        tab._load_preset("Copilot Premium")
        app.update()
        assert tab._card_dirty is False
    finally:
        tab._load_preset("MessageCannon Pro")


def test_editing_content_after_a_preset_load_marks_the_card_dirty(app):
    tab = app.card_creator_tab
    try:
        tab._load_preset("MessageCannon Pro")
        app.update()
        assert tab._card_dirty is False

        sec = _price_section(tab)
        sec["data"]["_price"].set("$999")
        app.update()
        assert tab._card_dirty is True
    finally:
        tab._load_preset("MessageCannon Pro")


def test_switching_preset_with_no_unsaved_content_skips_the_confirmation(app, monkeypatch):
    """Item 17: must not nag when there's nothing real to lose -- right
    after a fresh preset load (the common "just browsing presets" case)."""
    tab = app.card_creator_tab
    asked = []
    monkeypatch.setattr(
        "src.ui.card_creator_tab.messagebox.askyesno",
        lambda *a, **k: asked.append(1) or True)
    try:
        tab._load_preset("MessageCannon Pro")
        app.update()
        assert tab._card_dirty is False

        tab._confirm_and_load_preset("Copilot Premium")
        app.update()

        assert not asked, "should not have asked for confirmation when nothing was dirty"
        assert tab._mname.get() == "Copilot Premium"
    finally:
        tab._load_preset("MessageCannon Pro")


def test_switching_preset_with_unsaved_content_asks_and_respects_cancel(app, monkeypatch):
    """The literal repro of Item 17: real edited content must not be
    silently discarded -- confirms the dialog is shown, and that declining
    it genuinely leaves the current card untouched."""
    tab = app.card_creator_tab
    asked = []
    monkeypatch.setattr(
        "src.ui.card_creator_tab.messagebox.askyesno",
        lambda *a, **k: asked.append(1) or False)  # simulate the user clicking "No"
    try:
        tab._load_preset("MessageCannon Pro")
        app.update()
        sec = _price_section(tab)
        sec["data"]["_price"].set("$999")  # a real edit -- this is what must not be lost
        app.update()
        assert tab._card_dirty is True

        tab._confirm_and_load_preset("Copilot Premium")
        app.update()

        assert asked, "expected a real confirmation dialog when content was dirty"
        assert tab._mname.get() == "MessageCannon Pro", (
            "declining the confirmation must leave the current card untouched")
        assert sec["data"]["_price"].get() == "$999"
    finally:
        tab._load_preset("MessageCannon Pro")


def test_switching_preset_with_unsaved_content_proceeds_on_confirm(app, monkeypatch):
    tab = app.card_creator_tab
    monkeypatch.setattr("src.ui.card_creator_tab.messagebox.askyesno", lambda *a, **k: True)
    try:
        tab._load_preset("MessageCannon Pro")
        app.update()
        sec = _price_section(tab)
        sec["data"]["_price"].set("$999")
        app.update()
        assert tab._card_dirty is True

        tab._confirm_and_load_preset("Copilot Premium")
        app.update()

        assert tab._mname.get() == "Copilot Premium", (
            "confirming the dialog should actually proceed with the preset switch")
    finally:
        tab._load_preset("MessageCannon Pro")


def test_ai_generation_still_applies_directly_without_a_confirmation_prompt(app, monkeypatch):
    """AI generation applying its own freshly-drafted content is a
    different, intended flow from clicking a preset button -- it must not
    be blocked by this same confirmation (out of scope for Item 17, which
    is specifically about the preset-switch click)."""
    tab = app.card_creator_tab
    asked = []
    monkeypatch.setattr(
        "src.ui.card_creator_tab.messagebox.askyesno",
        lambda *a, **k: asked.append(1) or True)
    try:
        tab._load_preset("MessageCannon Pro")
        app.update()
        sec = _price_section(tab)
        sec["data"]["_price"].set("$999")
        app.update()
        assert tab._card_dirty is True

        tab._apply_ai_card_copy({
            "icon": "🎯", "tagline": "AI Tagline", "description": "AI description.",
            "features": ["A", "B"], "price": "$1", "old_price": "", "price_note": "",
            "style_name": "Dark Premium",
        })
        app.update()

        assert not asked, "AI generation must apply directly, not go through the preset-switch confirmation"
        assert tab._mtag.get() == "AI Tagline"
    finally:
        tab._load_preset("MessageCannon Pro")


def test_new_section_inserts_at_its_canonical_position_not_appended_at_the_end(app):
    """Item 22 of the Live Testing Findings pass (Round 2): adding a
    section must land it in a sensible position automatically, not always
    at the very end requiring manual reordering. Removes the Price section
    from a freshly-loaded preset (which already has one in the canonical
    spot), then re-adds it via the real "Add Section" path -- it must land
    back between Text/Features and Links/Contact, not after Contact."""
    tab = app.card_creator_tab
    try:
        tab._load_preset("MessageCannon Pro")
        app.update()
        price_sec = _price_section(tab)
        tab._remove_section(price_sec["frame"])
        app.update()

        types_before = [s["type"] for s in tab._sections]
        assert "price" not in types_before

        tab._add_section("price")
        app.update()

        types_after = [s["type"] for s in tab._sections]
        price_index = types_after.index("price")
        contact_index = types_after.index("contact")
        features_index = types_after.index("features")
        assert price_index < contact_index, (
            f"Price landed at index {price_index}, after Contact (index {contact_index}) -- "
            f"full order was {types_after}")
        assert price_index > features_index, (
            f"Price landed before Features (index {features_index}) -- full order was {types_after}")
    finally:
        tab._load_preset("MessageCannon Pro")


def test_adding_a_second_section_of_the_same_type_appends_after_the_first(app):
    """Same-type sections must keep a stable, predictable relative order
    (new ones after existing ones of the same type), not get shuffled."""
    tab = app.card_creator_tab
    try:
        tab._load_preset("MessageCannon Pro")
        app.update()
        tab._add_section("text")
        app.update()

        types = [s["type"] for s in tab._sections]
        text_indices = [i for i, t in enumerate(types) if t == "text"]
        assert len(text_indices) == 2
        assert text_indices == sorted(text_indices)  # adjacent/stable, not scattered
        assert types.index("contact") > text_indices[-1], (
            "the new Text section must still land before Contact")
    finally:
        tab._load_preset("MessageCannon Pro")


def test_advanced_sections_are_collapsed_by_default(app):
    """Item 24 follow-up: the user explicitly chose a real collapse toggle
    over just the relabel -- the section-builder body must be genuinely
    unmapped (not just visually de-emphasized) the first time Cards is
    shown, so a new user's first look is the AI box/presets/gallery only."""
    tab = app.card_creator_tab
    assert tab._sections_advanced_expanded is False
    assert not tab._sections_body.winfo_ismapped()
    assert tab._adv_toggle_btn.cget("text") == "▶  Show"


def test_toggle_advanced_sections_shows_and_hides_the_body(app):
    tab = app.card_creator_tab
    try:
        assert not tab._sections_body.winfo_ismapped()

        tab._toggle_advanced_sections()
        app.update()
        assert tab._sections_advanced_expanded is True
        assert tab._sections_body.winfo_ismapped()
        assert tab._adv_toggle_btn.cget("text") == "▼  Hide"

        tab._toggle_advanced_sections()
        app.update()
        assert tab._sections_advanced_expanded is False
        assert not tab._sections_body.winfo_ismapped()
        assert tab._adv_toggle_btn.cget("text") == "▶  Show"
    finally:
        if tab._sections_advanced_expanded:
            tab._toggle_advanced_sections()


def test_sections_area_is_labeled_advanced(app):
    """Item 24: the manual section-builder must read as the power-user
    path, not the main experience -- the AI box/presets/template gallery
    above it are the primary, easy path."""
    tab = app.card_creator_tab

    def walk(widget):
        for child in widget.winfo_children():
            if isinstance(child, ctk.CTkLabel):
                try:
                    if "Advanced" in str(child.cget("text")):
                        return True
                except Exception:
                    pass
            if walk(child):
                return True
        return False

    assert walk(tab), 'expected a real "Advanced" label near the section-builder toolbar'


def test_card_with_many_sections_stays_scrollable_and_reachable(app):
    """Item 24's other explicit ask: the full card must remain properly
    scrollable/visible within its panel at all times, even with a real
    14-section card (the user's own reported scenario) -- matching the
    Item 18 scroll fix already applied to the Card Identity panel above."""
    tab = app.card_creator_tab
    try:
        tab._load_preset("MessageCannon Pro")  # 7 sections
        app.update()
        if not tab._sections_advanced_expanded:
            tab._toggle_advanced_sections()  # must be expanded to be reachable at all
        for stype in ("text", "features", "banner", "links", "text", "features", "price"):
            tab._add_section(stype)
        app.update()

        assert len(tab._sections) == 14
        assert isinstance(tab._sections_scroll, ctk.CTkScrollableFrame)
        # Every section, including the last one added, must be a real,
        # grid-managed (reachable-by-scrolling) widget -- not clipped or
        # silently dropped from layout.
        for sec in tab._sections:
            assert sec["frame"].winfo_manager() == "grid"
            assert sec["frame"].winfo_ismapped()
    finally:
        if tab._sections_advanced_expanded:
            tab._toggle_advanced_sections()
        tab._load_preset("MessageCannon Pro")


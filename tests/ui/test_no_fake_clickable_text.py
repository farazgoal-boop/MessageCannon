"""Real bug found via live feedback: several plain, non-interactive text
elements throughout the app were styled in `T.ACCENT_TEXT` -- this app's
own real, established "this is a clickable link/action" color (see
"Configure in Settings ->", "View recipient list ->", "Get an API key ->",
all real `CTkButton`s with a genuine `command=`) -- with no click handler
at all, visually implying an action that didn't exist.

Audited every `text_color=T.ACCENT_TEXT`/`T.ACCENT` usage across
`main_window.py`, `card_creator_tab.py`, `ai_compose_dialog.py`, and
`update_dialog.py` (via an AST scan, not just grep, to reliably tell a
`CTkButton` from a `CTkLabel`). Confirmed two large, legitimate, and
genuinely different categories are NOT this bug and were left alone:
badge/pill chips (`fg_color=T.BADGE_BG` + `corner_radius=999`-ish, e.g.
"45 sec cadence", "Live Monitoring") and bare KPI/stat-value numbers under
a muted label (e.g. Settings/Dashboard stat tiles) -- neither reads as a
link to a real user, and both are already-established, consistent visual
languages elsewhere in this app. The real, confirmed instances of the "fake
link" bug, fixed here:

1. The sidebar's "Pro | Campaign Suite" tagline (the originally reported
   one) -- a plain descriptor, not a navigable destination.
2. Card Creator's per-section "↕" reorder icon -- a classic drag-handle
   glyph, but the real reorder mechanism is the real ↑/↓ buttons right next
   to it; the icon itself has no drag support at all.
3. Card Creator's "▶ Video will play inside the card" caption -- a play
   icon implying "click to preview", but it's just descriptive text about
   export-time behavior.
4. Card Creator's "Contact footer uses your info from App Identity above."
   caption -- a plain explanatory note with nothing to click.
5. The license-activation dialog's "If you close the app without
   activating..." notice -- plain informational text (not even a real
   warning -- T.DANGER_ON_BADGE is this app's real warning color, used a
   few lines below it for a genuine error message).
6. The license-activation dialog's "Secure local activation" card heading
   -- every other info-card heading in this app (e.g. Settings' "Session
   Status") uses T.TEXT_HEAD, not the link color.
"""

from __future__ import annotations

import customtkinter as ctk

import src.ui.theme as T


def _find_label_by_text(widget, text):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel):
            try:
                if child.cget("text") == text:
                    return child
            except Exception:
                pass
        found = _find_label_by_text(child, text)
        if found is not None:
            return found
    return None


def test_sidebar_tagline_is_not_styled_as_a_fake_link(app):
    label = app._brand_subtitle_label
    assert label.cget("text_color") == T.TEXT_MUTED
    assert label.cget("text_color") != T.ACCENT_TEXT


def test_card_creator_reorder_icon_is_not_styled_as_a_fake_drag_handle(app):
    tab = app.card_creator_tab
    icon = _find_label_by_text(tab, "↕")
    assert icon is not None, "expected to find the section reorder '↕' icon"
    assert icon.cget("text_color") == T.TEXT_MUTED
    assert icon.cget("text_color") != T.ACCENT_TEXT


def test_card_creator_video_caption_is_not_styled_as_a_fake_link(app):
    tab = app.card_creator_tab
    # Ensure at least one youtube-type section exists to find the caption in.
    tab._load_preset("SaaS Product")
    try:
        found_any_youtube_caption = False
        for sec in tab._sections:
            caption = _find_label_by_text(sec["frame"], "▶ Video will play inside the card")
            if caption is not None:
                found_any_youtube_caption = True
                assert caption.cget("text_color") == T.TEXT_MUTED
                assert caption.cget("text_color") != T.ACCENT_TEXT
        if not found_any_youtube_caption:
            # The default preset doesn't include a youtube section -- add
            # one directly to exercise this specific caption. Item 22's
            # "smart insertion order" means the new section isn't
            # necessarily appended at the end of the list -- search all
            # sections, not just the last one.
            tab._add_section("youtube")
            app.update()
            caption = None
            for sec in tab._sections:
                caption = _find_label_by_text(sec["frame"], "▶ Video will play inside the card")
                if caption is not None:
                    break
            assert caption is not None
            assert caption.cget("text_color") == T.TEXT_MUTED
    finally:
        tab._load_preset("SaaS Product")


def test_card_creator_contact_footer_caption_is_not_styled_as_a_fake_link(app):
    tab = app.card_creator_tab
    tab._add_section("contact")
    app.update()
    try:
        # Item 22's "smart insertion order" means the new section isn't
        # necessarily appended at the end -- search all sections.
        caption = None
        for sec in tab._sections:
            caption = _find_label_by_text(
                sec["frame"], "Contact footer uses your info from App Identity above.")
            if caption is not None:
                break
        assert caption is not None
        assert caption.cget("text_color") == T.TEXT_MUTED
        assert caption.cget("text_color") != T.ACCENT_TEXT
    finally:
        tab._load_preset("SaaS Product")


def test_license_dialog_notice_and_heading_are_not_styled_as_fake_links(app):
    app.license_dialog = None
    app._show_license_gate()
    app.update()
    try:
        dialog = app.license_dialog
        assert dialog is not None

        notice = _find_label_by_text(
            dialog,
            "If you close the app without activating, the workspace "
            "remains locked until a valid activation code is entered.")
        assert notice is not None
        assert notice.cget("text_color") == T.TEXT_MUTED
        assert notice.cget("text_color") != T.ACCENT_TEXT

        heading = _find_label_by_text(dialog, "Secure, machine-bound activation")
        assert heading is not None
        assert heading.cget("text_color") == T.TEXT_HEAD
        assert heading.cget("text_color") != T.ACCENT_TEXT
    finally:
        if app.license_dialog is not None and app.license_dialog.winfo_exists():
            app.license_dialog.grab_release()
            app.license_dialog.destroy()
        app.license_dialog = None
        app.update()

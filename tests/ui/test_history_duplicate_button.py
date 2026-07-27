"""Item 12 of the Live Testing Findings pass (Round 2): History's
"Duplicate" button read as plain text, not a clearly clickable button.

Root cause, measured (not guessed): the button's own `fg_color=T.BADGE_BG`
fill had only ~1.2:1 contrast against its row's `T.BG_INNER` background (the
two tokens are near-identical shades in both Dark and Light) -- the
button's rectangular shape was nearly invisible regardless of its text
color. Fixed by matching the outline-button style already established
elsewhere in the app (Compose's Pause/Resume button): a real border +
accent-colored text, which measures ~3.2-4.0:1 contrast against T.BG_INNER
in both themes -- a token-only fix, no new hex values.
"""

from __future__ import annotations

import customtkinter as ctk

import src.ui.theme as T


def _find_button_by_text(widget, text):
    if isinstance(widget, ctk.CTkButton):
        try:
            if widget.cget("text") == text:
                return widget
        except Exception:
            pass
    for child in widget.winfo_children():
        found = _find_button_by_text(child, text)
        if found is not None:
            return found
    return None


def test_duplicate_button_styled_as_a_real_clickable_outline_button(app):
    original_campaigns = getattr(app, "_history_campaigns", None)
    original_channel = app._compose_channel_var.get()
    original_subject = app._em_subj_var.get()
    original_view = app._active_view
    try:
        app._show_view("History")
        app.update()
        app._history_campaigns = [{
            "name": "Test Campaign", "created_at": "2026-01-01",
            "sent_count": 5, "failed_count": 0,
            "message_template": "Hello {name}",
        }]
        app._render_history_rows()
        app.update()

        button = _find_button_by_text(app.view_containers["History"], "↻ Duplicate")
        assert button is not None, "expected a real 'Duplicate' button in History"

        # The real fix: a visible border + accent text, not a
        # near-invisible flat fill. text_color is T.ACCENT_TEXT (Item 27 of
        # the Final Premium Polish Pass), not plain T.ACCENT -- plain ACCENT
        # measured only 3.20:1 against this row's real T.BG_INNER background
        # in Dark mode, an accepted-at-the-time borderline value (the
        # WCAG large-text/UI-component floor, not full AA); ACCENT_TEXT
        # passes full AA comfortably (7.16:1) on the same background.
        assert button.cget("fg_color") == "transparent"
        assert button.cget("border_width") >= 1
        assert button.cget("border_color") == T.ACCENT
        assert button.cget("text_color") == T.ACCENT_TEXT
    finally:
        if original_campaigns is not None:
            app._history_campaigns = original_campaigns
            app._render_history_rows()
        app._compose_channel_var.set(original_channel)
        app._on_channel_switch(original_channel)
        app._em_subj_var.set(original_subject)
        app._show_view(original_view)
        app.update()


def test_duplicate_button_still_works_functionally(app):
    """Confirms the restyle didn't break the actual duplicate action."""
    original_campaigns = getattr(app, "_history_campaigns", None)
    original_channel = app._compose_channel_var.get()
    original_subject = app._em_subj_var.get()
    original_view = app._active_view
    try:
        app._show_view("History")
        app.update()
        app._history_campaigns = [{
            "name": "Test Campaign", "created_at": "2026-01-01",
            "sent_count": 5, "failed_count": 0,
            "message_template": "Hello {name}, special offer!",
        }]
        app._render_history_rows()
        app.update()

        button = _find_button_by_text(app.view_containers["History"], "↻ Duplicate")
        button._command()
        app.update()

        assert app._em_subj_var.get() == "Hello {name}, special offer!"
        assert app._compose_channel_var.get() == "Email"
        assert app._active_view == "Compose"
    finally:
        if original_campaigns is not None:
            app._history_campaigns = original_campaigns
            app._render_history_rows()
        app._compose_channel_var.set(original_channel)
        app._on_channel_switch(original_channel)
        app._em_subj_var.set(original_subject)
        app._show_view(original_view)
        app.update()

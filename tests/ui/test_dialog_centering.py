"""Regression coverage for Item 7 of the Live Testing Findings pass: the main
window and dialogs (Import Contacts, Generate with AI, etc.) opened wherever
the window manager defaulted them (normally the screen's top-left corner)
instead of centered.

`tests/ui/test_window_utils.py` already covers the shared `center_on_parent`/
`center_on_screen` helpers in isolation; this file drives real dialogs
against the real `app` fixture to confirm they're actually wired up, not
just that the helper itself works.
"""

from __future__ import annotations

from src.ui.ai_compose_dialog import AIComposeDialog
from src.ui.confirm_dialogs import DangerConfirmDialog
from src.ui.contact_import_review import ContactImportReviewDialog


def _is_centered_on(dialog, parent, width, height, tolerance=5) -> bool:
    """`width`/`height` are the *logical* (pre-DPI-scaling) size the dialog
    was constructed with -- CustomTkinter's `.geometry()` override silently
    scales width/height (but not position) by its own per-monitor DPI
    factor (see `window_utils.py`'s module docstring for the full story), so
    expected position must be computed from the dialog's real, already-
    scaled size. Uses `_apply_window_scaling` directly (the same
    deterministic, non-timing-dependent source `center_on_parent` itself
    uses) rather than a live `winfo_width()` read -- confirmed by direct
    reproduction that a freshly-created `CTkToplevel`'s `winfo_width()`
    can still report CTk's un-rendered 200x200 placeholder immediately
    after `.update()`, making a live-read comparison flaky for exactly the
    kind of just-constructed dialog this test drives."""
    dialog.update_idletasks()
    parent.update_idletasks()
    scale = getattr(dialog, "_apply_window_scaling", None)
    real_w = scale(width) if callable(scale) else width
    real_h = scale(height) if callable(scale) else height
    expected_x = parent.winfo_x() + (parent.winfo_width() - real_w) // 2
    expected_y = parent.winfo_y() + (parent.winfo_height() - real_h) // 2
    expected_x = max(0, expected_x)
    expected_y = max(0, expected_y)
    return (abs(dialog.winfo_x() - expected_x) <= tolerance
            and abs(dialog.winfo_y() - expected_y) <= tolerance)


def test_ai_compose_dialog_opens_centered_on_main_window(app):
    dialog = AIComposeDialog(app, "whatsapp", on_pick=lambda *_: None)
    try:
        assert _is_centered_on(dialog, app, 620, 600)
    finally:
        dialog.destroy()
        app.update()


def test_contact_import_review_dialog_opens_centered_on_main_window(app):
    dialog = ContactImportReviewDialog(app)
    try:
        assert _is_centered_on(dialog, app, 760, 680)
    finally:
        dialog.destroy()
        app.update()


def test_danger_confirm_dialog_opens_centered_on_main_window(app):
    dialog = DangerConfirmDialog(
        app, "Test Title", "Test message", "DELETE", "Delete", on_confirm=lambda: None)
    try:
        assert _is_centered_on(dialog, app, 440, 320)
    finally:
        dialog.destroy()
        app.update()


def test_main_window_itself_is_centered_on_screen(app):
    app.update_idletasks()
    screen_w = app.winfo_screenwidth()
    screen_h = app.winfo_screenheight()
    expected_x = max(0, (screen_w - app.winfo_width()) // 2)
    expected_y = max(0, (screen_h - app.winfo_height()) // 2)
    assert abs(app.winfo_x() - expected_x) <= 5
    assert abs(app.winfo_y() - expected_y) <= 5

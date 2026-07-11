"""Danger Zone typed-confirmation safety: the destructive action button must
stay disabled until the exact confirmation word is typed, and Escape must
cancel cleanly. Uses the shared session `app` — never actually completes a
destructive action against it (would corrupt every later test); only tests
the confirmation dialog's own gating logic."""

import tkinter as tk

import customtkinter as ctk


def _find_button_by_text(root, text):
    for widget in root.winfo_children():
        if isinstance(widget, ctk.CTkButton) and text in str(widget.cget("text")):
            return widget
        found = _find_button_by_text(widget, text)
        if found is not None:
            return found
    return None


def _find_entry(root):
    for widget in root.winfo_children():
        if isinstance(widget, ctk.CTkEntry):
            return widget
        found = _find_entry(widget)
        if found is not None:
            return found
    return None


def _find_toplevel(window):
    for child in window.children.values():
        if isinstance(child, tk.Toplevel):
            return child
    return None


def test_delete_all_contacts_dialog_requires_exact_confirmation_word(app):
    stray = _find_toplevel(app)
    if stray is not None:
        stray.destroy()
    app._show_view("Settings")
    app.update()

    button = _find_button_by_text(app, "Delete All Contacts")
    assert button is not None, "Delete All Contacts button not found in Settings"
    button._command()
    app.update()

    dialog = _find_toplevel(app)
    assert dialog is not None, "confirmation dialog did not open"
    try:
        action_button = _find_button_by_text(dialog, "Delete All Contacts")
        assert action_button.cget("state") == "disabled"

        entry = _find_entry(dialog)
        entry.insert(0, "wrong text")
        app.update()
        assert action_button.cget("state") == "disabled", (
            "action button must stay disabled for incorrect confirmation text")

        entry.delete(0, "end")
        entry.insert(0, "DELETE")
        app.update()
        assert action_button.cget("state") == "normal", (
            "action button should enable once the exact word is typed")
    finally:
        # Always close via Escape/destroy — never click the enabled button,
        # which would really delete every contact in the shared test window.
        dialog.destroy()


def test_danger_dialog_escape_cancels_without_action(app):
    stray = _find_toplevel(app)
    if stray is not None:
        stray.destroy()
    app._show_view("Settings")
    app.update()

    button = _find_button_by_text(app, "Clear Campaign History")
    assert button is not None
    button._command()
    app.update()

    dialog = _find_toplevel(app)
    assert dialog is not None
    dialog.event_generate("<Escape>")
    app.update()

    assert _find_toplevel(app) is None, "Escape should close the danger dialog"

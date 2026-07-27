"""Item 14 of the Live Testing Findings pass (Round 2): theme switching
flickered through multiple inconsistent visual states before settling.

Two real root causes found via direct instrumentation (not guessed):

1. CustomTkinter's own ctk_base_class.py._set_appearance_mode() calls
   update_idletasks() once per live CTk widget on every
   ctk.set_appearance_mode() call. With ~540+ CTk widgets alive at once
   (every view is built upfront, not just the active one), that's ~540+
   sequential partial-screen-repaint flushes -- measured at 350-1000ms
   wall-clock for set_appearance_mode() alone. Mitigated with a solid,
   already-correct-destination-color overlay (_show_theme_switch_overlay)
   that covers the screen for the duration of the switch, matching the
   close-button fix's own "hide the slow operation" pattern.

2. The dominant cause, found by reading CustomTkinter's ctk_tk.py: on
   Windows, CTk's root window calls _windows_set_titlebar_color() on every
   appearance-mode change (so the native OS title bar tracks Dark/Light) --
   and that method calls the real tkinter withdraw()/deiconify() on the
   WHOLE WINDOW to force the OS to redraw the title bar. Confirmed directly:
   our own overlay frame (a child of the window) went from mapped=1 right
   after being shown to mapped=0 immediately after ctk.set_appearance_mode()
   ran -- only possible if the ANCESTOR window itself was withdrawn. Fixed
   by setting self._deactivate_windows_window_header_manipulation = True in
   __init__ -- CTk's own documented escape hatch for this exact method.
   Disclosed trade-off: the native title bar no longer actively tracks the
   in-app theme.
"""

from __future__ import annotations

import customtkinter as ctk


def test_deactivate_windows_titlebar_manipulation_is_set(app):
    """The real fix for the dominant cause -- without this, CTk withdraws
    the whole window on every appearance-mode change."""
    assert app._deactivate_windows_window_header_manipulation is True


def test_overlay_is_shown_with_destination_color_before_switch_completes(app):
    original_theme = app.theme_var.get()
    try:
        app._apply_theme("Dark")
        assert app._theme_switch_overlay is not None
        assert app._theme_switch_overlay.winfo_ismapped()
        assert app._theme_switch_overlay.cget("bg").upper() == "#0F1419"
        app.update()  # flush the after_idle-deferred hide
        assert not app._theme_switch_overlay.winfo_ismapped()

        app._apply_theme("Light")
        assert app._theme_switch_overlay.winfo_ismapped()
        assert app._theme_switch_overlay.cget("bg").upper() == "#F4F6FA"
        app.update()
        assert not app._theme_switch_overlay.winfo_ismapped()
    finally:
        app._apply_theme(original_theme)
        app.update()


def test_overlay_stays_mapped_through_the_real_appearance_mode_call(app):
    """The literal repro of root cause #2: confirm the overlay (a direct
    child of the window) is still mapped immediately after
    ctk.set_appearance_mode() returns -- if the whole window had been
    withdrawn, this would report False."""
    original_theme = app.theme_var.get()
    try:
        app._show_theme_switch_overlay("Dark")
        assert app._theme_switch_overlay.winfo_ismapped()

        ctk.set_appearance_mode("Dark")
        assert app._theme_switch_overlay.winfo_ismapped(), (
            "overlay was unmapped mid-switch -- the whole window was "
            "withdrawn during ctk.set_appearance_mode(), reintroducing "
            "the flicker this fix is supposed to eliminate")

        app._sync_theme_overrides()
        assert app._theme_switch_overlay.winfo_ismapped()

        app._hide_theme_switch_overlay()
        assert not app._theme_switch_overlay.winfo_ismapped()
    finally:
        app._apply_theme(original_theme)
        app.update()


def test_warm_ivory_rebuild_path_also_masks_and_then_hides(app):
    original_theme = app.theme_var.get()
    try:
        app._on_theme_selected("Warm Ivory")
        assert app._theme_switch_overlay.winfo_ismapped()
        app.update()  # flush the after_idle-deferred full rebuild
        assert not app._theme_switch_overlay.winfo_ismapped()
        assert app.winfo_exists()
    finally:
        app._on_theme_selected(original_theme)
        app.update()


def test_repeated_toggles_always_end_with_overlay_hidden(app):
    """The user's explicit ask: 5-10 consecutive switches must stay stable,
    not degrade or leave the overlay stuck visible."""
    original_theme = app.theme_var.get()
    try:
        for i in range(8):
            target = "Light" if i % 2 == 0 else "Dark"
            app._apply_theme(target)
            app.update()
            assert not app._theme_switch_overlay.winfo_ismapped(), (
                f"overlay left stuck visible after switch #{i + 1} ({target})")
    finally:
        app._apply_theme(original_theme)
        app.update()


def test_system_mode_overlay_color_does_not_raise(app):
    """"System" mode has no single fixed destination -- confirm the
    fallback path (darkdetect, or its own except-fallback) never raises."""
    original_theme = app.theme_var.get()
    try:
        color = app._theme_switch_overlay_color("System")
        assert color.startswith("#")
    finally:
        app._apply_theme(original_theme)
        app.update()

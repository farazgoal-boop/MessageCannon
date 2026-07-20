"""Round 2 item 7 (broad cross-theme polish audit): a real, severe bug found
via direct instrumentation, not code reading -- Dark<->Light theme toggling
silently stopped working for most widget colors after the very first theme
rebuild (i.e. after the app has ever entered/left Warm Ivory, which happens
on the very first launch since Warm Ivory is the fresh-install default).

Root cause: MainWindow._sync_theme_overrides() (called by
_rebuild_ui_for_theme right after every full rebuild, and by _apply_theme
on every plain Dark<->Light toggle) walks the entire widget tree and, for
each color attribute, unconditionally collapsed a (light, dark) tuple -- the
whole point of which is that CTk auto-resolves it natively on
ctk.set_appearance_mode() with zero extra code -- down to a single string
matching whichever mode was active at that moment, via
widget.configure(fg_color=<single string>). Once flattened, that widget's
color is no longer a tuple, so it can never again respond to a native
appearance-mode change; it stays frozen until the next full rebuild
recreates it. Since _rebuild_ui_for_theme calls _sync_theme_overrides
immediately after building fresh widgets, this happened on literally every
theme rebuild, meaning: build widgets (dynamic tuple, correct) -> sync flattens
them (static string, frozen) -> any later plain Dark<->Light toggle (no
rebuild) does nothing visible.

Verified via direct probe before writing this fix: a Settings card's
fg_color stayed frozen at "#2A4762" (the Dark value) after switching to
Light, both immediately after _apply_theme("Light") and after manually
forcing _sync_theme_overrides() again. Fixed by having _sync_widget_theme
skip any attribute whose current value is already a tuple/list -- those are
CTk-native and must be left alone; only plain strings (CTk's own
"gray98"-style hardcoded defaults, or a legacy THEME_COLOR_PAIRS literal)
actually need the manual remap this method exists for.
"""

import tkinter as tk

import customtkinter as ctk
import pytest


def _close_any_toplevel(window) -> None:
    def walk(widget):
        for child in widget.children.values():
            if isinstance(child, tk.Toplevel):
                return child
            found = walk(child)
            if found:
                return found
        return None
    top = walk(window)
    if top is not None:
        top.destroy()


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    """Module-scoped (not function-scoped): more than ~2-3 sequential
    tkinter root-window creations in one process is unreliable here (see
    tests/ui/README.md). Each test resets to a known "just rebuilt, Warm
    Ivory" starting point via _on_theme_selected("Warm Ivory") rather than
    getting a fresh window, since switching *to* Warm Ivory from any other
    palette also triggers a full rebuild -- exactly the precondition each
    test needs (a freshly rebuilt widget, tuple-valued fg_color intact)."""
    from src.database import db_manager as db_manager_module

    mp = pytest.MonkeyPatch()
    fresh_db_path = str(tmp_path_factory.mktemp("theme_toggle") / "test.db")
    mp.setattr(db_manager_module, "get_database_path", lambda: fresh_db_path)
    db_manager_module.DatabaseManager._instance = None

    from src.ui.main_window import MainWindow

    win = MainWindow()
    _close_any_toplevel(win)
    win.update()
    try:
        yield win
    finally:
        try:
            if win.winfo_exists():
                win.destroy()
        except Exception:
            pass
        db_manager_module.DatabaseManager._instance = None
        mp.undo()


def _reset_to_freshly_rebuilt_warm_ivory(window) -> None:
    window._on_theme_selected("Warm Ivory")
    window.update()


def _find_labelled_card(widget, label_text):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkLabel) and child.cget("text") == label_text:
            return widget
        found = _find_labelled_card(child, label_text)
        if found:
            return found
    return None


def test_widget_color_survives_dark_light_toggle_after_rebuild(window):
    """The exact reproduction: fresh install is Warm Ivory (a rebuild
    happens on the very first theme change away from it), then Dark (another
    rebuild, since leaving Warm Ivory), then Light (a plain sync, no
    rebuild) -- the bug only showed up on this third step."""
    _reset_to_freshly_rebuilt_warm_ivory(window)
    window._show_view("Settings")
    window.update()

    window._on_theme_selected("Dark")
    window.update()
    window._show_view("Settings")
    window.update()

    card = _find_labelled_card(window, "Campaign Safety")
    assert card is not None
    fg_after_dark = card.cget("fg_color")
    assert isinstance(fg_after_dark, (tuple, list)), (
        "a freshly rebuilt widget's fg_color should be a (light, dark) tuple, "
        f"got {fg_after_dark!r}")
    assert fg_after_dark[1] == "#2A4762"  # dark half of T.BG_SURFACE

    window._on_theme_selected("Light")
    window.update()

    fg_after_light = card.cget("fg_color")
    assert isinstance(fg_after_light, (tuple, list)), (
        "fg_color was flattened from a tuple into a static string by the "
        f"Dark->Light toggle -- got {fg_after_light!r}. This means the "
        "widget can never respond to a future appearance-mode change again.")
    assert fg_after_light[0] == "#FFFFFF"  # light half of T.BG_SURFACE
    assert fg_after_light == fg_after_dark, (
        "the tuple itself must be unchanged across a plain (non-rebuild) "
        "theme toggle -- only which half CTk renders should change")


def test_theme_toggle_actually_changes_rendered_color(window):
    """Not just that the tuple survives -- that CTk really does render the
    other half after a plain Dark<->Light toggle with no rebuild."""
    _reset_to_freshly_rebuilt_warm_ivory(window)
    window._show_view("Settings")
    window.update()

    window._on_theme_selected("Dark")
    window.update()
    window._show_view("Settings")
    window.update()

    card = _find_labelled_card(window, "Campaign Safety")
    canvas = getattr(card, "_canvas", None)
    assert canvas is not None
    # "inner_parts" is CTkFrame's own canvas tag for its fg_color-filled
    # shapes, distinct from "border_parts" -- found by direct inspection of
    # CTkFrame's canvas item tags, not guessed.
    fill_dark = canvas.itemcget(canvas.find_withtag("inner_parts")[0], "fill")
    assert fill_dark.upper() == "#2A4762"

    window._on_theme_selected("Light")
    window.update()

    fill_light = canvas.itemcget(canvas.find_withtag("inner_parts")[0], "fill")
    assert fill_light.upper() == "#FFFFFF", (
        f"card still rendered {fill_light!r} after switching to Light -- "
        "the Dark<->Light toggle isn't actually changing the visible color")

"""Part 3: on a completely fresh install with no saved preference, the app
must launch in the Warm Ivory light theme, not dark.

Found while writing this test (not assumed from the doc's framing): the
real default was "Dark" in two places — the theme_var StringVar's initial
value and _load_settings()'s fallback when no settings row exists yet.
Fixed both; this test exercises the fix against a genuinely fresh,
isolated database (not the real app DB, which already has saved
preferences from prior use and would never expose this bug)."""

import tkinter as tk

from src.ui import theme as T


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


def test_fresh_install_defaults_to_warm_ivory_light_theme(tmp_path, monkeypatch):
    from src.database import db_manager as db_manager_module

    fresh_db_path = str(tmp_path / "fresh_install.db")
    monkeypatch.setattr(db_manager_module, "get_database_path", lambda: fresh_db_path)
    db_manager_module.DatabaseManager._instance = None  # bypass the singleton
    # so MainWindow's DatabaseManager() call below actually re-inits against
    # the fresh path instead of returning the already-initialized singleton.

    from src.ui.main_window import MainWindow

    window = MainWindow()
    try:
        _close_any_toplevel(window)
        window.update()

        assert window.theme_var.get() == "Warm Ivory", (
            f"fresh install theme_var was {window.theme_var.get()!r}, expected 'Warm Ivory'")
        assert T.get_palette() == "warm_ivory", (
            f"fresh install active palette was {T.get_palette()!r}, expected 'warm_ivory'")
    finally:
        try:
            if window.winfo_exists():
                window.destroy()
        except Exception:
            pass
        db_manager_module.DatabaseManager._instance = None

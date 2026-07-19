"""Split out from test_sidebar_collapse.py because this is the one test in
that area that genuinely needs two sequential MainWindow() root creations
(before/after "restart") -- keeping it in its own file/process avoids
stacking it on top of that file's own module-scoped window and tripping the
"more than ~2-3 sequential Tk roots in one process" instability documented
in tests/ui/README.md."""

import tkinter as tk


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


def test_collapsed_state_persists_across_restart(tmp_path, monkeypatch):
    """Toggling collapse saves to the settings blob (_save_settings); a
    fresh MainWindow pointed at the same DB must reopen already collapsed."""
    from src.database import db_manager as db_manager_module

    fresh_db_path = str(tmp_path / "sidebar_collapse_persist_test.db")
    monkeypatch.setattr(db_manager_module, "get_database_path", lambda: fresh_db_path)
    db_manager_module.DatabaseManager._instance = None

    from src.ui.main_window import MainWindow

    window1 = MainWindow()
    _close_any_toplevel(window1)
    window1.update()
    try:
        assert window1._sidebar_collapsed is False
        window1._toggle_sidebar_collapsed()
        window1.update()
        assert window1._sidebar_collapsed is True
    finally:
        try:
            if window1.winfo_exists():
                window1.destroy()
        except Exception:
            pass
    db_manager_module.DatabaseManager._instance = None

    window2 = MainWindow()
    _close_any_toplevel(window2)
    window2.update()
    try:
        assert window2._sidebar_collapsed is True, (
            "a fresh MainWindow against the same DB should reopen with the "
            "sidebar still collapsed -- persistence via sidebar_collapsed "
            "in the settings blob is broken")
        assert window2.sidebar_collapse_btn.cget("text") == "»"
    finally:
        try:
            if window2.winfo_exists():
                window2.destroy()
        except Exception:
            pass
        db_manager_module.DatabaseManager._instance = None

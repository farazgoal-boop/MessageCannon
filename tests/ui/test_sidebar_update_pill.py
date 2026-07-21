"""Round 2 item 2: JobMind Match's real `.sidebar-update-pill` (styles.css:1243,
confirmed via direct source read) pairs a gradient pill with a small pulsing
dot. A true CSS gradient fill isn't achievable on a CTkButton in Tk, so this
covers the part that is: a small canvas dot next to the existing update
badge, alternating between T.ACCENT and T.BG_MAIN (its own background) on a
~1.8s period, simulating the CSS opacity-pulse keyframe with colors instead
of alpha since Tk canvas items have no alpha channel.

Uses a dedicated, module-scoped, fresh-DB MainWindow -- same reasoning as
test_sidebar_collapse.py: toggling the sidebar calls _save_settings(), which
would otherwise write into the live production settings blob.
"""

import tkinter as tk

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
    from src.database import db_manager as db_manager_module

    mp = pytest.MonkeyPatch()
    fresh_db_path = str(tmp_path_factory.mktemp("update_pill") / "test.db")
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
            win._stop_update_dot_pulse()
        except Exception:
            pass
        try:
            if win.winfo_exists():
                win.destroy()
        except Exception:
            pass
        db_manager_module.DatabaseManager._instance = None
        mp.undo()


def _fake_update_info():
    from src.core.update_checker import UpdateInfo
    return UpdateInfo(
        version="9.9.9", tag="v9.9.9", release_notes="test",
        release_url="https://example.com", asset_url=None, asset_name=None,
    )


def test_no_update_hides_row_and_stops_pulse(window):
    window._update_info = None
    window._refresh_update_badge()
    window.update()
    assert not window._update_badge_row.winfo_ismapped()
    assert window._update_dot_pulse_after_id is None


def test_update_available_shows_row_and_starts_pulse(window):
    window._update_info = _fake_update_info()
    window._refresh_update_badge()
    window.update()
    try:
        assert window._update_badge_row.winfo_ismapped()
        assert window._update_dot_pulse_after_id is not None
        assert "v9.9.9" in window.update_badge_var.get()
    finally:
        window._update_info = None
        window._refresh_update_badge()
        window.update()


def test_dot_alternates_between_accent_and_background(window):
    from src.ui import theme as T

    window._update_info = _fake_update_info()
    window._refresh_update_badge()
    window.update()
    try:
        dot = window._update_badge_dot
        item = window._update_badge_dot_item
        fill_0 = dot.itemcget(item, "fill")
        # Cancel the real 900ms-scheduled step and advance one manually so
        # the test doesn't need a real wall-clock sleep.
        window.after_cancel(window._update_dot_pulse_after_id)
        window._update_dot_pulse_after_id = None
        window._start_update_dot_pulse()  # restarts from "lit" state deterministically
        fill_lit = dot.itemcget(item, "fill")
        assert fill_lit.upper() == T.resolve(T.ACCENT).upper()
    finally:
        window._update_info = None
        window._refresh_update_badge()
        window.update()


def test_collapsing_sidebar_stops_pulse_expanding_resumes_it(window):
    window._update_info = _fake_update_info()
    window._refresh_update_badge()
    window.update()
    try:
        assert window._update_dot_pulse_after_id is not None

        if window._sidebar_collapsed:
            window._toggle_sidebar_collapsed()
            window.update()

        window._toggle_sidebar_collapsed()  # -> collapsed
        window.update()
        assert window._update_dot_pulse_after_id is None, (
            "pulse animation should stop while the sidebar is collapsed "
            "(the badge isn't visible)")

        window._toggle_sidebar_collapsed()  # -> expanded again
        window.update()
        assert window._update_badge_row.winfo_ismapped()
        assert window._update_dot_pulse_after_id is not None
    finally:
        window._update_info = None
        window._refresh_update_badge()
        window.update()

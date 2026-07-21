"""Round 2 item 8: coverage for MainWindow._build_status_bar -- the
JobMind-Match-style `.footer-status-bar` equivalent (a full-width bar
pinned to the bottom of the whole window via grid row=1, columnspan=2,
built once in __init__ and never destroyed/rebuilt). Mirrors
test_sidebar_update_pill.py's structure/reasoning for the pulsing-dot
coverage.

Uses a dedicated, module-scoped, fresh-DB MainWindow -- same reasoning as
test_sidebar_collapse.py and test_sidebar_update_pill.py: this suite must
never touch the real production settings/database.
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


def _collect_label_texts(widget) -> list:
    texts = []
    for child in widget.winfo_children():
        try:
            text = child.cget("text")
        except Exception:
            text = None
        if text:
            texts.append(str(text))
        texts.extend(_collect_label_texts(child))
    return texts


@pytest.fixture(scope="module")
def window(tmp_path_factory):
    from src.database import db_manager as db_manager_module

    mp = pytest.MonkeyPatch()
    fresh_db_path = str(tmp_path_factory.mktemp("status_bar") / "test.db")
    mp.setattr(db_manager_module, "get_database_path", lambda: fresh_db_path)
    db_manager_module.DatabaseManager._instance = None

    from src.ui.main_window import MainWindow

    win = MainWindow()
    _close_any_toplevel(win)
    win.update()
    try:
        yield win
    finally:
        if getattr(win, "_status_bar_dot_pulse_after_id", None) is not None:
            try:
                win.after_cancel(win._status_bar_dot_pulse_after_id)
            except Exception:
                pass
        try:
            if win.winfo_exists():
                win.destroy()
        except Exception:
            pass
        db_manager_module.DatabaseManager._instance = None
        mp.undo()


def test_status_bar_exists_pinned_at_bottom(window):
    bar = window._status_bar_dot.master.master.master
    info = bar.grid_info()
    assert info.get("row") == 1
    assert int(info.get("columnspan", 1)) == 2
    assert bar.winfo_ismapped()


def test_status_bar_contains_expected_text_pieces(window):
    from src.utils.constants import APP_NAME, APP_VERSION, DEVELOPER

    bar = window._status_bar_dot.master.master.master
    texts = " ".join(_collect_label_texts(bar))
    assert APP_NAME in texts
    assert f"v{APP_VERSION}" in texts
    assert "100% On Your Device" in texts
    assert DEVELOPER in texts
    assert "Live" in texts


def test_status_bar_dot_pulses(window):
    from src.ui import theme as T

    assert window._status_bar_dot_pulse_after_id is not None

    dot = window._status_bar_dot
    item = window._status_bar_dot_item

    window.after_cancel(window._status_bar_dot_pulse_after_id)
    window._status_bar_dot_pulse_after_id = None
    window._start_status_bar_dot_pulse()  # restarts from "lit" state deterministically
    fill_lit = dot.itemcget(item, "fill")
    assert fill_lit.upper() == T.resolve(T.SUCCESS).upper()


def test_start_status_bar_dot_pulse_is_idempotent(window):
    first_id = window._status_bar_dot_pulse_after_id
    window._start_status_bar_dot_pulse()
    assert window._status_bar_dot_pulse_after_id == first_id

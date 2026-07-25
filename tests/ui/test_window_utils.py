"""Coverage for src/ui/window_utils.py -- Item 7 of the Live Testing
Findings pass (main window and dialogs weren't centered).

Uses real, mapped (not withdrawn) Tk windows -- a withdrawn window's
winfo_x()/winfo_y() don't reflect the geometry request reliably, since the
window manager hasn't actually placed it yet.

All three tests share a single module-scoped `tk.Tk()` root rather than
each creating its own: this suite's own `tests/ui/README.md` documents that
more than ~2-3 real `Tk()`/`CTk()` root windows created in sequence within
one process is unreliable ("Can't find a usable init.tcl"). An earlier
version of this file created a fresh `tk.Tk()` per test (3 across the file)
and hit exactly that limit under `-n <file-count> --dist loadfile` --
confirmed by re-running this file alone and seeing 2 of the 3 tests fail
with that exact TclError. `tk.Toplevel(root)` children don't carry the same
risk (they share the root's interpreter), so only ever one real root is
created per process here, same as every other test file in this suite.
"""

from __future__ import annotations

import tkinter as tk

import pytest

from src.ui.window_utils import center_on_parent, center_on_screen


@pytest.fixture(scope="module")
def root():
    window = tk.Tk()
    yield window
    window.destroy()


def test_center_on_screen_centers_within_bounds(root):
    top = tk.Toplevel(root)
    try:
        center_on_screen(top, 400, 300)
        top.update()
        screen_w, screen_h = top.winfo_screenwidth(), top.winfo_screenheight()
        expected_x = max(0, (screen_w - top.winfo_width()) // 2)
        expected_y = max(0, (screen_h - top.winfo_height()) // 2)
        assert abs(top.winfo_x() - expected_x) <= 2
        assert abs(top.winfo_y() - expected_y) <= 2
    finally:
        top.destroy()


def test_center_on_parent_centers_relative_to_a_real_parent(root):
    root.geometry("800x600+100+100")
    root.update()

    child = tk.Toplevel(root)
    try:
        center_on_parent(child, 400, 300, root)
        child.update()

        expected_x = root.winfo_x() + (root.winfo_width() - child.winfo_width()) // 2
        expected_y = root.winfo_y() + (root.winfo_height() - child.winfo_height()) // 2
        assert abs(child.winfo_x() - max(0, expected_x)) <= 2
        assert abs(child.winfo_y() - max(0, expected_y)) <= 2
    finally:
        child.destroy()


def test_center_on_parent_falls_back_to_screen_when_parent_has_no_real_geometry(root):
    class FakeParent:
        def update_idletasks(self):
            pass

        def winfo_width(self):
            return 1

        def winfo_height(self):
            return 1

    top = tk.Toplevel(root)
    try:
        center_on_parent(top, 400, 300, FakeParent())
        top.update()
        screen_w, screen_h = top.winfo_screenwidth(), top.winfo_screenheight()
        expected_x = max(0, (screen_w - top.winfo_width()) // 2)
        expected_y = max(0, (screen_h - top.winfo_height()) // 2)
        assert abs(top.winfo_x() - expected_x) <= 2
        assert abs(top.winfo_y() - expected_y) <= 2
    finally:
        top.destroy()

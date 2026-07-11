"""Part 2 regression test: the X button must hide the window near-instantly
(the actual fix — see CLAUDE.md), even though full background teardown can
still take longer while it safely finishes closing the WhatsApp session.

Uses its own dedicated MainWindow rather than the shared session `app`
fixture: _on_close() disables the window's close protocol and schedules its
real destruction (background thread + a 4s hard-deadline after() call) —
running that against the fixture shared by every other test in the suite
would leave a later test operating on a torn-down window."""

import time
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


MAX_PERCEIVED_CLOSE_MS = 500


def test_close_hides_window_near_instantly():
    from src.ui.main_window import MainWindow

    window = MainWindow()
    try:
        _close_any_toplevel(window)
        window.update()

        start = time.perf_counter()
        window._on_close()
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert elapsed_ms < MAX_PERCEIVED_CLOSE_MS, (
            f"_on_close() took {elapsed_ms:.1f}ms to return — should withdraw "
            f"the window near-instantly and finish teardown in the background")
        assert window.winfo_viewable() == 0, "window should be withdrawn (hidden) immediately"
    finally:
        try:
            if window.winfo_exists():
                window.destroy()
        except Exception:
            pass

"""Item 8 of the Live Testing Findings pass: "verify sidebar update badge
end-to-end" — drives the real path a user's click actually takes (sidebar
badge -> `UpdateDialog` -> Download & Install -> success/failure), not just
the badge's own show/hide/pulse mechanics already covered by
`test_sidebar_update_pill.py`.

Real bug found while doing this verification, not by reading the code and
assuming it was fine (the same discipline every other item in this pass has
used): `update_dialog.py`'s `_start_download`'s failure branch had the exact
deferred-lambda-closes-over-a-deleted-except-binding bug Item 3 of this same
pass found and fixed at 10 other call sites (`except Exception as exc: ...
self.after(0, lambda: ...(str(exc)))` — `exc` is deleted by Python at the end
of the `except` block, but `self.after(0, ...)` always defers past that point,
so referencing it raises a `NameError` that Tk's callback handler silently
swallows). This file predates Item 3's grep sweep and was missed. Fixed the
same way: capture `str(exc)` into a plain variable before deferring. See
`update_dialog.py`'s own comment at the fix site for the full account.

Uses a dedicated, module-scoped, fresh-DB MainWindow -- same reasoning as
`test_sidebar_update_pill.py`: this exercises real download-worker threads and
must never risk touching the live production database or settings.

Toast notifications (`show_toast`, itself a `CTkToplevel`) fired by the
failure path are real, separate top-level windows that auto-dismiss on their
own timer (~2.8s) -- these tests don't wait that long, so a `Toast` can
legitimately still exist as a sibling Toplevel when a later test runs.
`_find_update_dialog` filters by type (`UpdateDialog` specifically) rather
than "any Toplevel" so a lingering Toast is never mistaken for the dialog.
"""

from __future__ import annotations

import tkinter as tk
import time

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
    fresh_db_path = str(tmp_path_factory.mktemp("update_dialog_e2e") / "test.db")
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


class _SynchronousThread:
    """Stand-in for threading.Thread that runs `target` immediately, in the
    calling (main) thread, instead of spawning a real OS thread.

    Needed for the same reason Item 3's test_ai_error_reporting.py needed
    it: this harness drives Tk via `.update()` polling rather than a real
    `mainloop()`, and a *real* background thread's cross-thread `self.after()`
    registration requires Tcl to consider itself inside a running mainloop —
    confirmed directly earlier this session, not assumed. Running the
    "worker" synchronously in the main thread sidesteps that entirely while
    still exercising the exact same code path (including the real
    `self.after(0, ...)` marshalling calls) a real click would take.
    """

    def __init__(self, target=None, daemon=None):
        self._target = target

    def start(self):
        self._target()


def _fake_update_info(asset_url="https://example.invalid/MessageCannon_Setup.exe",
                       asset_name="MessageCannon_Setup.exe"):
    from src.core.update_checker import UpdateInfo
    return UpdateInfo(
        version="9.9.9", tag="v9.9.9",
        release_notes="- item one\n- item two",
        release_url="https://example.invalid/releases/v9.9.9",
        asset_url=asset_url, asset_name=asset_name,
    )


def _find_update_dialogs(window):
    from src.ui.update_dialog import UpdateDialog
    return [c for c in window.winfo_children() if isinstance(c, UpdateDialog)]


def _destroy_all_update_dialogs(window):
    for d in _find_update_dialogs(window):
        try:
            d.destroy()
        except Exception:
            pass
    window.update()


def _reset_update_state(window):
    _destroy_all_update_dialogs(window)
    window._update_info = None
    window._refresh_update_badge()
    window.update()


def _safe_text(widget):
    try:
        return widget.cget("text")
    except Exception:
        return None


def test_clicking_sidebar_badge_opens_real_dialog_with_correct_content(window):
    import customtkinter as ctk

    window._update_info = _fake_update_info()
    window._refresh_update_badge()
    window.update()
    try:
        assert window.sidebar_update_badge.cget("command") == window._show_update_dialog

        window._show_update_dialog()
        window.update()

        dialogs = _find_update_dialogs(window)
        assert len(dialogs) == 1, "clicking the badge must open exactly one real UpdateDialog"
        dialog = dialogs[0]
        assert dialog.title() == "Update available"

        texts = []

        def walk(widget):
            if isinstance(widget, ctk.CTkLabel):
                text = _safe_text(widget)
                if text:
                    texts.append(text)
            for child in widget.winfo_children():
                walk(child)

        walk(dialog)
        blob = "\n".join(texts)
        assert "v9.9.9" in blob
        assert "installed" in blob
    finally:
        _reset_update_state(window)


def test_download_failure_shows_real_message_not_swallowed_nameerror(window, monkeypatch):
    import src.ui.update_dialog as update_dialog_module

    monkeypatch.setattr(update_dialog_module.threading, "Thread", _SynchronousThread)

    def _boom(*_a, **_k):
        raise ConnectionError("simulated network failure")

    monkeypatch.setattr(update_dialog_module, "download_asset", _boom)

    window._update_info = _fake_update_info()
    window._refresh_update_badge()
    window.update()
    window._show_update_dialog()
    window.update()
    dialogs = _find_update_dialogs(window)
    assert len(dialogs) == 1
    dialog = dialogs[0]
    try:
        dialog._start_download()
        # The synchronous-thread stand-in means the worker (including its
        # self.after(0, ...) call) has already run by the time .start()
        # returns; one more update() lets that after()-scheduled callback
        # actually fire.
        window.update()

        status = dialog._status_var.get()
        assert status == "Download failed — you can try again or use \"View on GitHub\".", (
            f"expected the real failure message, got: {status!r} -- a blank/"
            f"unchanged status here would mean the NameError bug regressed")
        assert dialog._install_btn.cget("state") == "normal"
    finally:
        _reset_update_state(window)


def test_download_success_schedules_apply_update(window, monkeypatch):
    import src.ui.update_dialog as update_dialog_module

    monkeypatch.setattr(update_dialog_module.threading, "Thread", _SynchronousThread)
    monkeypatch.setattr(update_dialog_module, "download_asset",
                         lambda *_a, **_k: r"C:\fake\MessageCannon_Setup.exe")

    calls = []
    monkeypatch.setattr(window, "_apply_downloaded_update", lambda path: calls.append(path))

    window._update_info = _fake_update_info()
    window._refresh_update_badge()
    window.update()
    window._show_update_dialog()
    window.update()
    dialogs = _find_update_dialogs(window)
    assert len(dialogs) == 1
    dialog = dialogs[0]
    try:
        dialog._start_download()
        window.update()
        # _on_download_succeeded destroys the dialog itself and schedules
        # _apply_downloaded_update 600ms later on the main window -- wait
        # past that deadline using real after()-scheduled polling (not a
        # busy loop) the same way conftest's wait_for_view_animation does.
        deadline = time.time() + 2.0
        while not calls and time.time() < deadline:
            window.update()
        assert calls == [r"C:\fake\MessageCannon_Setup.exe"]
        assert _find_update_dialogs(window) == [], "dialog should have destroyed itself on success"
    finally:
        _reset_update_state(window)


def test_later_button_closes_dialog(window):
    window._update_info = _fake_update_info()
    window._refresh_update_badge()
    window.update()
    window._show_update_dialog()
    window.update()
    dialogs = _find_update_dialogs(window)
    assert len(dialogs) == 1
    dialog = dialogs[0]
    try:
        later_btn = None
        for child in dialog.winfo_children():
            for grandchild in child.winfo_children():
                if _safe_text(grandchild) == "Later":
                    later_btn = grandchild
        assert later_btn is not None, "could not locate the Later button"
        later_btn.invoke()
        window.update()
        assert not dialog.winfo_exists()
    finally:
        _reset_update_state(window)


def test_no_asset_disables_install_button_with_reason(window):
    window._update_info = _fake_update_info(asset_url=None, asset_name=None)
    window._refresh_update_badge()
    window.update()
    window._show_update_dialog()
    window.update()
    dialogs = _find_update_dialogs(window)
    assert len(dialogs) == 1
    dialog = dialogs[0]
    try:
        assert dialog._install_btn.cget("state") == "disabled"
        assert "No Windows installer" in dialog._status_var.get()
    finally:
        _reset_update_state(window)

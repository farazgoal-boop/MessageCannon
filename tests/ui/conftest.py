"""Shared fixtures for the UI/integration test suite.

Why not literal OS-level UI automation (pywinauto): verified empirically
before writing these tests — connected pywinauto to a real running instance
of this app via both the "uia" and "win32" backends and enumerated every
descendant control. CustomTkinter renders all of its widgets as shapes
drawn directly onto a Tk Canvas rather than as distinct native Win32/UWP
controls, so neither backend exposes any accessible name, role, or even a
non-empty window_text for a single one of the app's real buttons, labels,
or nav items (only generic, anonymous "Pane"/"Image" or "TkChild"/"Static"
elements with no identifying text — zero sidebar nav items were findable by
name). This is a structural limitation of CustomTkinter's rendering model
on Windows, not a bug in the test script; two backends were tried before
concluding this.

These tests instead call the exact same command callables/methods a real
click invokes, directly, in-process — the same technique used throughout
manual verification this session, formalized here so it can be re-run as a
regression suite. This is still testing the real, shipped production code
(PyInstaller bundles this exact source), just via direct invocation rather
than a simulated OS-level click, since no tool can perform the latter
against this UI framework on this platform.
"""

from __future__ import annotations

import os
import sys
import time
import tkinter as tk
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

# The real MainWindow.__init__ schedules a background GitHub Releases check
# (self.after(1200, self._start_update_check)) that does a real DNS+TLS+HTTP
# call. Patched to a no-op here, at import time, so it applies no matter which
# test file constructs its own MainWindow() (several do, not just the `app`
# fixture below) — a real external network call has no business running in
# an automated suite regardless of timing: it's slow, flaky offline/in CI,
# and was measured to push test_navigation_timing.py's Contacts/Cards
# transitions ~10-20ms over their 500ms budget from pure CPU/GIL contention
# with the request, the same class of interference already documented above
# for the WhatsApp session-bootstrap thread — confirmed by reverting this
# patch and re-running: the same two tests failed, reproducibly.
import src.ui.main_window as _main_window_module  # noqa: E402


def _no_op_update_check(*_args, **_kwargs):
    return None


_main_window_module.check_for_update = _no_op_update_check


def _close_any_toplevel(app) -> None:
    """Close the setup wizard (or any other startup Toplevel) if one opened,
    so tests start from the main window in a known state."""
    def walk(widget):
        for child in widget.children.values():
            if isinstance(child, tk.Toplevel):
                return child
            found = walk(child)
            if found:
                return found
        return None
    top = walk(app)
    if top is not None:
        top.destroy()


def wait_for_view_animation(window, timeout_s: float = 2.0) -> None:
    """Block until the current _animate_view_in() run finishes, using
    Tk-native after()-scheduled polling rather than a tight busy-wait loop.

    This matters for measurement accuracy, not just style: a busy-wait loop
    (`while ...: app.update(); time.sleep(0.003)`) was tried first and
    measured transitions at roughly 2x their real duration — repeatedly
    calling update() from a tight Python loop competes with Tk's own event
    processing. Switching to app.after()-scheduled polling (letting Tk
    decide when to actually check, same as how the real app or a mainloop-
    driven script would wait) cut the measured time for an identical,
    unchanged transition from 381.7ms to 163.8ms. Confirmed with a side by
    side comparison before changing the test, not assumed."""
    result = {}

    def check():
        if window._view_anim_after_id is None:
            result["done"] = True
        else:
            window.after(5, check)

    window.after(5, check)
    deadline = time.time() + timeout_s
    while "done" not in result and time.time() < deadline:
        window.update()


@pytest.fixture(scope="session")
def app():
    """A single, real, shared MainWindow instance for the whole test run.

    Session-scoped rather than fresh-per-test on purpose, not for speed:
    creating and destroying multiple independent ctk.CTk()/tkinter.Tk() root
    windows in sequence within one process is unreliable — verified
    empirically while writing this suite (a fresh MainWindow() per test
    worked for the first several tests, then failed with "Can't find a
    usable init.tcl" on a later one, a known class of Tcl-interpreter
    lifecycle issue with repeated root creation, not an app bug). One
    shared window avoids it entirely.

    Tests that need real isolation (writing contacts/campaigns, changing
    theme/settings) must use the `isolated_db` fixture and/or explicitly
    save+restore whatever app state they mutate, rather than relying on a
    fresh window. A handful of tests that specifically need to observe
    *fresh-install* behavior (e.g. the default theme) construct their own
    dedicated MainWindow — see test_light_theme_default.py — since that is
    exactly what they're testing and can't be done against a shared,
    already-initialized instance."""
    from src.ui.main_window import MainWindow

    window = MainWindow()
    _close_any_toplevel(window)
    window.update()

    # MainWindow.__init__ schedules self.after(900, self._maybe_show_setup_wizard)
    # — a real, one-time delayed reopen (the real app's DB in this environment
    # has setup_wizard_completed=False, left that way deliberately per Phase 1
    # for the user's own first-run testing). Left alone, that timer can fire
    # in the middle of an unrelated test, mid-assertion, rather than at fixture
    # setup where it's expected. Wait past the 900ms mark once here and close
    # whatever it opens, so every test starts from a known, wizard-free state.
    deadline = time.time() + 1.2
    while time.time() < deadline:
        window.update()
    _close_any_toplevel(window)
    window.update()

    yield window
    try:
        if window.winfo_exists():
            window.destroy()
    except Exception:
        pass


@pytest.fixture()
def isolated_db(tmp_path, monkeypatch):
    """A throwaway SQLite DB for tests that need to write data without ever
    touching the real user database. Returns a DatabaseManager instance
    pointed at a temp file. Use this instead of `app.db` whenever a test
    needs to insert/delete rows — DatabaseManager is a singleton keyed on
    process state, so this constructs one manually with an isolated path
    rather than risk any write reaching the real production database."""
    from src.database.db_manager import DatabaseManager

    db = DatabaseManager.__new__(DatabaseManager)
    db.db_path = str(tmp_path / "test_messagecannon.db")
    db._initialize_database()
    return db

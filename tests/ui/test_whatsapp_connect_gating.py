"""Item 31 (2026-07-28): the app was auto-launching a real, forced-maximize
Chrome browser 800ms after EVERY MainWindow construction, unconditionally --
including for a user who had never connected WhatsApp at all. Traced while
investigating a real report that the user's Windows taskbar/shell became
unresponsive during/after this suite's own parallel run: confirmed live on
this machine that Selenium/chromedriver/Chrome genuinely function here, so
every real MainWindow (test or app) was silently spawning a real automated
browser on startup.

Fix: MainWindow._start_session_bootstrap now only proceeds with the real
WhatsAppSender.initialize() call if SessionManager.get_session_state() (a
pure local file/DB read, no browser involved) reports an already-verified,
unexpired session -- otherwise it just updates the status text and returns.
Connecting for the first time (or after logout/expiry) now only ever
happens via an explicit action: the new "Connect WhatsApp" button
(_connect_whatsapp_now), the Setup Wizard's own WhatsApp step, or actually
starting a real send (WhatsAppSender.send_messages calls initialize()
itself, unaffected by this gate).

conftest.py already patches WhatsAppSender.initialize to a no-op globally
(the direct fix for the taskbar-affecting bug) -- these tests monkeypatch
it further, per-test, to a spy so they can assert whether it WAS called,
not just that it's harmless if it is.
"""

from __future__ import annotations

import time

import customtkinter as ctk

from src.session_manager import SessionState


class _SynchronousThread:
    """Stand-in for threading.Thread -- runs the target immediately on the
    calling thread. Needed because this harness drives Tk via app.update()
    polling, not a real mainloop(); a genuine background thread's
    self.after() call raises "main thread is not in main loop" here even
    though the identical code works fine in the real app. Same stand-in
    already used by test_ai_error_reporting.py/test_update_dialog_e2e.py."""

    def __init__(self, target=None, daemon=None, **_kwargs):
        self._target = target

    def start(self):
        self._target()


def _set_session_active(app, active: bool) -> None:
    if active:
        state = SessionState(True, None, False, "Active session available")
    else:
        state = SessionState(False, None, True, "Session expired - please scan QR")
    app.whatsapp_sender.get_session_state = lambda: state


def _find_button(widget, text):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton) and child.cget("text") == text:
            return child
        found = _find_button(child, text)
        if found:
            return found
    return None


def test_start_session_bootstrap_skips_real_launch_with_no_verified_session(app, monkeypatch):
    """The literal repro of the bug: a user who has never connected (or
    whose session expired/logged out) must not trigger a real browser
    launch just from the app starting up."""
    import src.ui.main_window as mw_module

    monkeypatch.setattr(mw_module.threading, "Thread", _SynchronousThread)
    _set_session_active(app, False)
    calls = []
    monkeypatch.setattr(app.whatsapp_sender, "initialize", lambda: calls.append(1))
    app.license_locked = False

    app._start_session_bootstrap()
    app.update()

    assert calls == [], "initialize() must never be called when no verified session exists"
    assert "Connect WhatsApp" in app.session_status_var.get()


def test_start_session_bootstrap_reconnects_with_a_verified_session(app, monkeypatch):
    """The legitimate case this gate must still allow: an already-verified,
    unexpired session should keep auto-reconnecting on startup exactly as
    before -- this item narrows the auto-launch, it doesn't remove it."""
    import src.ui.main_window as mw_module

    monkeypatch.setattr(mw_module.threading, "Thread", _SynchronousThread)
    _set_session_active(app, True)
    calls = []

    def fake_initialize():
        calls.append(1)
        return SessionState(True, None, False, "Active session available")

    monkeypatch.setattr(app.whatsapp_sender, "initialize", fake_initialize)
    app.license_locked = False

    app._start_session_bootstrap()
    app.update()

    assert calls == [1], "initialize() must still be called when a verified session exists"


def test_connect_whatsapp_now_always_launches_regardless_of_saved_state(app, monkeypatch):
    """The new explicit trigger: clicking "Connect WhatsApp" must connect
    even with no previously-verified session -- that's the whole point of
    moving the trigger to an explicit action instead of blocking it
    entirely."""
    import src.ui.main_window as mw_module

    monkeypatch.setattr(mw_module.threading, "Thread", _SynchronousThread)
    _set_session_active(app, False)
    calls = []

    def fake_initialize():
        calls.append(1)
        return SessionState(True, None, False, "Active session available")

    monkeypatch.setattr(app.whatsapp_sender, "initialize", fake_initialize)

    app._show_view("Settings")
    app.update()
    btn = _find_button(app, "🔗 Connect WhatsApp")
    assert btn is not None, "Connect WhatsApp button must exist in Settings"

    btn.invoke()
    app.update()

    assert calls == [1]
    assert btn.cget("text") == "🔗 Connect WhatsApp"
    assert btn.cget("state") == "normal"


def test_connect_button_disables_during_connect(app, monkeypatch):
    """While a real connect is in flight, the button must show it's busy
    (matching the existing Test-key/Testing... pattern elsewhere in
    Settings), not stay clickable and silent."""
    import src.ui.main_window as mw_module

    seen_state_during_call = {}

    app._show_view("Settings")
    app.update()
    btn = _find_button(app, "🔗 Connect WhatsApp")

    monkeypatch.setattr(mw_module.threading, "Thread", _SynchronousThread)
    _set_session_active(app, False)

    def fake_initialize():
        seen_state_during_call["text"] = btn.cget("text")
        seen_state_during_call["state"] = btn.cget("state")
        return SessionState(True, None, False, "Active session available")

    monkeypatch.setattr(app.whatsapp_sender, "initialize", fake_initialize)

    btn.invoke()
    app.update()

    assert seen_state_during_call["text"] == "Connecting…"
    assert seen_state_during_call["state"] == "disabled"
    # restored afterward
    assert btn.cget("text") == "🔗 Connect WhatsApp"
    assert btn.cget("state") == "normal"


def test_send_messages_path_is_unaffected_by_the_startup_gate(app):
    """WhatsAppSender.send_messages() calls self.initialize() directly (not
    through MainWindow._start_session_bootstrap), so an explicit "Start
    Sending" campaign action must remain completely unaffected by this
    item's gating -- confirmed by reading the real send_messages source,
    not assumed."""
    import inspect

    from src.core.whatsapp_sender import WhatsAppSender

    src_text = inspect.getsource(WhatsAppSender.send_messages)
    assert "self.initialize()" in src_text

"""Regression coverage for Item 3 of the Live Testing Findings pass: "Test
key" and "Generate with AI" appeared to show a raw "None" (or, root-caused
here, sometimes nothing at all) instead of a real result.

Real root cause, found by direct reproduction (not guessed): every AI
failure path in the app followed the same buggy shape --

    except AIServiceError as ex:
        self.after(0, lambda: something(str(ex)))

`except ... as ex` bindings are auto-deleted by Python at the end of the
except block (CPython does this unconditionally, even when a closure
references the name) -- but `self.after(0, ...)` defers the lambda to the
next Tk idle tick, which always runs *after* the except block has already
exited. By the time the lambda runs, `ex` no longer exists: referencing it
raises `NameError`, which Tk's default callback-exception handler prints to
stderr and otherwise silently swallows (invisible in a windowed/frozen
build). The fix, applied identically at all 10 real call sites found via a
`grep` sweep (main_window.py x3, card_creator_tab.py x4,
ai_compose_dialog.py x1, contact_import_review.py x2): compute `str(ex)`
into a plain variable *inside* the except block, before deferring, and
reference that variable in the lambda instead of `ex` itself.
"""

from __future__ import annotations

import threading
import time

import customtkinter as ctk
import pytest

from src.core.ai_service import AIServiceError
from src.ui.ai_compose_dialog import AIComposeDialog


def _find_button(widget, text):
    for child in widget.winfo_children():
        if isinstance(child, ctk.CTkButton) and child.cget("text") == text:
            return child
        found = _find_button(child, text)
        if found:
            return found
    return None


def _pump_until(app, predicate, timeout_s: float = 3.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        app.update()
        if predicate():
            return True
        time.sleep(0.02)
    return False


class _SynchronousThread:
    """Stand-in for threading.Thread that runs the target immediately, on
    the calling (main) thread, instead of spawning a real OS thread.

    Needed because this test harness drives the app via `app.update()`
    polling rather than a real `mainloop()` -- cross-thread `self.after()`
    registration requires Tcl to consider itself "in" a running mainloop,
    which manual `update()` polling never establishes (confirmed directly:
    a real background thread's `self.after()` call raises "RuntimeError:
    main thread is not in main loop" in this harness even though the same
    code works fine in the real, `mainloop()`-driven app). Running the
    worker synchronously sidesteps that harness limitation while still
    exercising the exact real except/lambda/after code path this item's fix
    is about -- only the concurrency, not the logic under test, is stubbed."""

    def __init__(self, target=None, daemon=None, **_kwargs):
        self._target = target

    def start(self):
        self._target()


def test_except_as_binding_is_really_deleted_before_deferred_lambda_runs():
    """Proves the underlying Python mechanism this whole item hinges on --
    not specific to this app, just confirms the CPython behavior being
    guarded against is real on the interpreter this app actually runs on."""
    class Err(Exception):
        pass

    captured = {}
    try:
        raise Err("boom")
    except Err as ex:
        def late():
            captured["result"] = str(ex)  # noqa: B023 -- deliberately reproducing the bug
        deferred = late

    with pytest.raises(NameError):
        deferred()


def test_settings_test_key_shows_real_error_on_failure(app, monkeypatch):
    import src.ui.main_window as mw_module

    calls = []
    monkeypatch.setattr(mw_module.messagebox, "showerror", lambda *a, **k: calls.append(("error", a)))
    monkeypatch.setattr(mw_module.messagebox, "showinfo", lambda *a, **k: calls.append(("info", a)))
    monkeypatch.setattr(mw_module.threading, "Thread", _SynchronousThread)

    def fake_validate(_key, provider="anthropic"):
        raise AIServiceError("Invalid API key. Check the key saved in Settings.")

    monkeypatch.setattr(mw_module.ai_service, "validate_api_key", fake_validate)

    app._ai_api_key.set("some-saved-key")
    app._show_view("Settings")
    app.update()

    btn = _find_button(app, "Test key")
    assert btn is not None
    btn._command()

    assert _pump_until(app, lambda: len(calls) > 0), "no messagebox call was made -- error was swallowed"
    kind, args = calls[0]
    assert kind == "error"
    assert "Invalid API key" in args[1]
    assert "None" not in args[1]


def test_settings_test_key_shows_real_success_message(app, monkeypatch):
    import src.ui.main_window as mw_module

    calls = []
    monkeypatch.setattr(mw_module.messagebox, "showerror", lambda *a, **k: calls.append(("error", a)))
    monkeypatch.setattr(mw_module.messagebox, "showinfo", lambda *a, **k: calls.append(("info", a)))
    monkeypatch.setattr(mw_module.threading, "Thread", _SynchronousThread)
    monkeypatch.setattr(mw_module.ai_service, "validate_api_key", lambda _key, provider="anthropic": True)

    app._ai_api_key.set("some-saved-key")
    app._show_view("Settings")
    app.update()

    btn = _find_button(app, "Test key")
    btn._command()

    assert _pump_until(app, lambda: len(calls) > 0)
    kind, args = calls[0]
    assert kind == "info"
    assert "valid" in args[1].lower()


def test_ai_compose_dialog_shows_real_error_not_swallowed(app, monkeypatch):
    import src.ui.ai_compose_dialog as dlg_module

    monkeypatch.setattr(dlg_module.threading, "Thread", _SynchronousThread)

    def fake_generate(*_a, **_k):
        raise AIServiceError("Rate limited by Anthropic. Wait a moment and try again.")

    monkeypatch.setattr(dlg_module.ai_service, "generate_message_variations", fake_generate)

    dialog = AIComposeDialog(app, "whatsapp", on_pick=lambda *_: None)
    app.update()
    try:
        dialog._brief_box.delete("1.0", "end")
        dialog._brief_box.insert("1.0", "Remind customers about renewal")
        dialog._generate()

        assert _pump_until(app, lambda: dialog._status_var.get() != "")
        message = dialog._status_var.get()
        assert "Rate limited" in message
        assert message.strip() != "⚠"  # not just the prefix with an empty/missing message
    finally:
        dialog.destroy()
        app.update()

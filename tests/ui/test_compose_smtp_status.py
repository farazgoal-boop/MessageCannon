"""Regression coverage for Item 4 of the Live Testing Findings pass:
Compose's "SMTP connection" chip showed "Not configured" even when Settings/
the Setup Wizard had already confirmed a real, working SMTP connection.

Real root cause, found by reading `_build_compose_view` directly: the chip's
`_em_smtp_status_var` is only ever updated reactively, via
`self._em_user.trace_add("write", _smtp_changed)` — but `_em_user`/
`_em_provider` are already loaded from saved settings (`_load_settings()`,
called once at startup, before Compose is first built) by the time this
trace is registered, so the trace never fires for that already-loaded
value. The chip stayed stuck on its hardcoded "Not configured" default
until something else happened to re-touch those StringVars later (e.g.
actually retyping the SMTP username in Settings while Compose was open).
There was never a second, divergent source of truth — `_start_email_from_
compose`'s own send gate already reads the exact same `_em_user`/`_em_pass`
StringVars — just a missing initial sync of the display to it.

Fix: call `_smtp_changed()` once immediately after registering the traces.
"""

from __future__ import annotations


def test_compose_smtp_chip_reflects_already_configured_smtp_on_build(app):
    """The literal repro: configure SMTP first (as Settings/the Wizard would
    have already done), THEN build/rebuild the Compose view, and confirm the
    chip shows the real state immediately -- not the stale default."""
    original_user = app._em_user.get()
    original_provider = app._em_provider.get()
    try:
        app._em_user.set("realuser@gmail.com")
        app._em_provider.set("Gmail")

        app._build_compose_view()
        app.update()

        assert app._em_smtp_status_var.get() != "Not configured"
        assert "realuser@gmail.com" in app._em_smtp_status_var.get()
    finally:
        app._em_user.set(original_user)
        app._em_provider.set(original_provider)
        app._build_compose_view()
        app.update()


def test_compose_smtp_chip_shows_not_configured_when_actually_unconfigured(app):
    original_user = app._em_user.get()
    try:
        app._em_user.set("")
        app._build_compose_view()
        app.update()

        assert app._em_smtp_status_var.get() == "Not configured"
    finally:
        app._em_user.set(original_user)
        app._build_compose_view()
        app.update()


def test_compose_send_gate_uses_the_same_source_of_truth_as_the_chip(app):
    """Confirms there was never a second, divergent SMTP-config source --
    _start_email_from_compose's own gate reads the identical StringVars the
    chip now correctly syncs against."""
    from src.models import Contact

    original_user = app._em_user.get()
    original_contacts = app.contacts
    try:
        app._em_user.set("")
        app._build_compose_view()
        app.update()
        assert app._em_smtp_status_var.get() == "Not configured"

        # Guarantee the SMTP gate is actually reached regardless of what the
        # real DB happens to contain (an empty email-contact list would
        # return earlier, at a different check, for an unrelated reason).
        app.contacts = [Contact(phone="", email="someone@test.dev", name="Someone")]
        app._start_email_from_compose()
        assert "SMTP not configured" in app.progress_status_var.get()
    finally:
        app._em_user.set(original_user)
        app.contacts = original_contacts
        app._build_compose_view()
        app.update()

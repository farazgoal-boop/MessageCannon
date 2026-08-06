"""Item 36 of the multi-product generalization pass: real first-time
license/key activation UI, matching JobMind Match's proven request-code /
activation-code pattern (studied from its real source before building any
of this). Drives the real `_show_license_gate` dialog end to end -- never
against the real production license.lic file (a throwaway temp path is
monkeypatched in for the duration of each test that actually activates).
"""

from __future__ import annotations

import base64
import tempfile
from pathlib import Path

import customtkinter as ctk
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from src.utils import license_crypto
from src.utils.license_manager import LicenseManager


def _destroy(widget) -> None:
    try:
        if widget.winfo_exists():
            widget.destroy()
    except Exception:
        pass


def test_license_gate_shows_a_real_request_code(app):
    app.license_dialog = None
    app._show_license_gate()
    app.update()
    try:
        code = app.license_request_code_var.get()
        assert code.startswith("MCP-")
        assert code == LicenseManager.get_request_code()
        assert app.license_request_entry.cget("state") == "readonly"
    finally:
        _destroy(app.license_dialog)
        app.license_dialog = None


def test_license_gate_copy_button_copies_the_real_request_code(app):
    app.license_dialog = None
    app._show_license_gate()
    app.update()
    try:
        app._copy_license_request_code()
        app.update()
        clipboard_value = app.clipboard_get()
        assert clipboard_value == app.license_request_code_var.get()
    finally:
        _destroy(app.license_dialog)
        app.license_dialog = None


def test_license_gate_entry_placeholder_says_activation_code_not_passkey(app):
    app.license_dialog = None
    app._show_license_gate()
    app.update()
    try:
        assert app.license_entry.cget("placeholder_text") == "Enter activation code"
    finally:
        _destroy(app.license_dialog)
        app.license_dialog = None


def test_real_end_to_end_first_time_activation_through_the_real_dialog(app, monkeypatch):
    """The literal proof required by Item 36: a real request code shown in
    the real dialog, a "seller"-signed activation code (real Ed25519
    signature, throwaway test key -- never the real production signing
    key) entered into the real entry widget, the real "Activate Now"
    button's own method called -- and the dialog closes with a real
    licensed state, all without ever touching the real production
    license.lic file (redirected to an isolated temp path for this test's
    duration only)."""
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    monkeypatch.setattr(license_crypto, "PUBLIC_KEY_B64",
                         base64.b64encode(public_bytes).decode("ascii"))

    tmp_dir = tempfile.TemporaryDirectory()
    tmp_license_path = Path(tmp_dir.name) / "license.lic"
    monkeypatch.setattr(LicenseManager, "get_license_path", staticmethod(lambda: tmp_license_path))

    original_license_info = getattr(app, "license_info", None)
    original_locked = app.license_locked
    try:
        app.license_dialog = None
        app._show_license_gate()
        app.update()

        request_code = app.license_request_code_var.get()
        signature = private_key.sign(license_crypto._normalize_code(request_code).encode("utf-8"))
        activation_code = license_crypto.format_activation_code(signature)

        app.license_entry.delete(0, "end")
        app.license_entry.insert(0, activation_code)
        app._submit_license_activation()
        app.update()

        assert app.license_locked is False
        assert app.license_info["is_valid"] is True
        assert app.license_info["status"] == "licensed"
        assert app.license_dialog is None, "the dialog must close itself on a real successful activation"

        # "A second launch remembers it, not re-prompted" -- proven here as
        # a fresh check_license() read against the same real (temp) file
        # the activation above just wrote, independent of any in-memory
        # state left over from the activation call itself.
        fresh_status = LicenseManager.check_license()
        assert fresh_status["is_valid"] is True
        assert fresh_status["status"] == "licensed"
    finally:
        app.license_info = original_license_info
        app.license_locked = original_locked
        tmp_dir.cleanup()


def test_invalid_activation_code_keeps_the_dialog_open_with_a_real_error(app, monkeypatch):
    tmp_dir = tempfile.TemporaryDirectory()
    tmp_license_path = Path(tmp_dir.name) / "license.lic"
    monkeypatch.setattr(LicenseManager, "get_license_path", staticmethod(lambda: tmp_license_path))
    try:
        app.license_dialog = None
        app._show_license_gate()
        app.update()

        app.license_entry.delete(0, "end")
        app.license_entry.insert(0, "ACT-TOTALLY-FAKE-CODE")
        app._submit_license_activation()
        app.update()

        assert app.license_dialog is not None and app.license_dialog.winfo_exists()
        assert app.license_message_var.get() != ""
    finally:
        _destroy(app.license_dialog)
        app.license_dialog = None
        tmp_dir.cleanup()

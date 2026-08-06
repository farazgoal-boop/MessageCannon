"""Tests for license key validation."""

from __future__ import annotations

import base64
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from src.utils import license_crypto
from src.utils.license_manager import LicenseManager
from src.utils.constants import PAID_PASSKEY, TRIAL_DAYS


class TestLicense(unittest.TestCase):
    """License manager tests."""

    def test_trial_days_constant(self) -> None:
        self.assertEqual(TRIAL_DAYS, 3)

    def test_invalid_key_rejected(self) -> None:
        result = LicenseManager.activate_license("INVALID-KEY-0000")
        self.assertFalse(result.get("success"))

    def test_legacy_passkey_still_accepted_for_backward_compatibility(self) -> None:
        """Item 36: real existing customers who already activated under the
        old shared-passkey scheme must not be silently locked out by this
        fix -- see license_manager.py's own comment on why this fallback
        exists and why it can't be used to newly activate an install (the
        UI never shows/accepts this format for a new activation)."""
        self.assertTrue(LicenseManager._verify_license_key(PAID_PASSKEY))


class TestLicenseCryptoActivation(unittest.TestCase):
    """Item 36: the real Ed25519 request/activation-code flow, end to end,
    against a throwaway test keypair and an isolated temp license file --
    never the real seller signing key or the real user's own license.lic."""

    def setUp(self) -> None:
        self._original_public_key = license_crypto.PUBLIC_KEY_B64
        self._private_key = Ed25519PrivateKey.generate()
        public_bytes = self._private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        license_crypto.PUBLIC_KEY_B64 = base64.b64encode(public_bytes).decode("ascii")

        self._tmp_dir = tempfile.TemporaryDirectory()
        self._tmp_license_path = Path(self._tmp_dir.name) / "license.lic"
        self._original_get_license_path = LicenseManager.get_license_path
        LicenseManager.get_license_path = staticmethod(lambda: self._tmp_license_path)

    def tearDown(self) -> None:
        license_crypto.PUBLIC_KEY_B64 = self._original_public_key
        LicenseManager.get_license_path = self._original_get_license_path
        self._tmp_dir.cleanup()

    def _sign(self, request_code: str) -> str:
        signature = self._private_key.sign(license_crypto._normalize_code(request_code).encode("utf-8"))
        return license_crypto.format_activation_code(signature)

    def test_get_request_code_returns_a_real_mcp_prefixed_code(self) -> None:
        code = LicenseManager.get_request_code()
        self.assertTrue(code.startswith("MCP-"))

    def test_real_end_to_end_activation_with_a_seller_signed_code(self) -> None:
        """The literal proof required: request code -> "seller" signs it ->
        activation succeeds -> check_license reports a real commercial
        license, all against a real (throwaway) Ed25519 keypair, never a
        mock of the verification itself."""
        request_code = LicenseManager.get_request_code()
        activation_code = self._sign(request_code)

        result = LicenseManager.activate_license(activation_code)
        self.assertTrue(result.get("success"), result.get("message"))

        status = LicenseManager.check_license()
        self.assertTrue(status["is_valid"])
        self.assertFalse(status["is_trial"])
        self.assertEqual(status["status"], "licensed")

    def test_activation_code_for_a_different_machine_is_rejected(self) -> None:
        forged_for_another_machine = self._sign("MCP-00000-00000-00000-00000")
        result = LicenseManager.activate_license(forged_for_another_machine)
        self.assertFalse(result.get("success"))
        self.assertIn("computer", result.get("message", "").lower())

    def test_second_launch_after_activation_remembers_it_without_reprompting(self) -> None:
        """Proof required: "a second launch showing it's remembered (not
        re-prompted)" -- simulated here as a fresh check_license() call
        (exactly what a real second app launch does), reading back the
        same real license file written by the first activation."""
        request_code = LicenseManager.get_request_code()
        activation_code = self._sign(request_code)
        LicenseManager.activate_license(activation_code)

        # Simulate a fresh app launch: a brand-new check_license() call,
        # independent of any in-memory state from the activation above.
        status_on_relaunch = LicenseManager.check_license()
        self.assertTrue(status_on_relaunch["is_valid"])
        self.assertEqual(status_on_relaunch["status"], "licensed")

    def test_deactivate_reverts_to_an_expired_trial_not_a_fresh_one(self) -> None:
        request_code = LicenseManager.get_request_code()
        activation_code = self._sign(request_code)
        LicenseManager.activate_license(activation_code)

        result = LicenseManager.deactivate_license()
        self.assertTrue(result.get("success"))
        status = LicenseManager.check_license()
        self.assertFalse(status["is_valid"])
        self.assertEqual(status["status"], "expired")


if __name__ == "__main__":
    unittest.main()

"""Tests for license key validation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.license_manager import LicenseManager
from src.utils.constants import PAID_PASSKEY, TRIAL_DAYS


class TestLicense(unittest.TestCase):
    """License manager tests."""

    def test_trial_days_constant(self) -> None:
        self.assertEqual(TRIAL_DAYS, 3)

    def test_invalid_key_rejected(self) -> None:
        result = LicenseManager.activate_license("INVALID-KEY-0000")
        self.assertFalse(result.get("success"))

    def test_valid_passkey_accepted(self) -> None:
        self.assertTrue(LicenseManager._verify_license_key(PAID_PASSKEY))


if __name__ == "__main__":
    unittest.main()

"""Tests for SMTP config validation."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.modules.email_sender import SMTPConfig, BulkEmailSender


class TestEmailSender(unittest.TestCase):
    """SMTP configuration validation tests."""

    def test_valid_config(self) -> None:
        config = SMTPConfig(
            host="smtp.gmail.com",
            port=587,
            username="user@gmail.com",
            password="secret",
            sender_name="Test",
            sender_email="user@gmail.com",
        )
        self.assertEqual(config.validate(), [])

    def test_missing_host(self) -> None:
        config = SMTPConfig(
            host="",
            port=587,
            username="user@gmail.com",
            password="secret",
            sender_name="Test",
            sender_email="user@gmail.com",
        )
        errors = config.validate()
        self.assertTrue(any("host" in error.lower() for error in errors))

    def test_test_connection_invalid_host(self) -> None:
        config = SMTPConfig(
            host="invalid.invalid",
            port=587,
            username="user@test.com",
            password="secret",
            sender_name="Test",
            sender_email="user@test.com",
        )
        sender = BulkEmailSender()
        ok, message = sender.test_connection(config)
        self.assertFalse(ok)
        self.assertTrue(len(message) > 0)


if __name__ == "__main__":
    unittest.main()

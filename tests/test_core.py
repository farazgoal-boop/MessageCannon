"""
Unit tests for MessageCannon application.
"""

import unittest
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime
from unittest.mock import patch

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.validators import PhoneValidator, DataValidator
from models import Contact, Campaign, Template
from utils.license_manager import LicenseManager
from utils.constants import PAID_PASSKEY, TRIAL_DAYS


class TestPhoneValidator(unittest.TestCase):
    """Test phone validation functionality."""
    
    def test_valid_pakistan_format(self):
        """Test valid Pakistan phone format."""
        valid_phones = [
            "+923001234567",
            "+923105551234",
            "+923215678901",
        ]
        
        for phone in valid_phones:
            self.assertTrue(
                PhoneValidator.is_valid_pakistan_format(phone),
                f"Failed for: {phone}"
            )
    
    def test_invalid_pakistan_format(self):
        """Test invalid Pakistan phone formats."""
        invalid_phones = [
            "03001234567",
            "923001234567",
            "+92300",
            "+9230012345678",
        ]
        
        for phone in invalid_phones:
            self.assertFalse(
                PhoneValidator.is_valid_pakistan_format(phone),
                f"Should fail for: {phone}"
            )
    
    def test_normalize_phone(self):
        """Test phone normalization."""
        # Test leading zero conversion
        phone, error = PhoneValidator.normalize_phone("03001234567")
        self.assertEqual(phone, "+923001234567")
        self.assertEqual(error, "")
    
    def test_detect_duplicates(self):
        """Test duplicate phone detection."""
        phones = [
            "+923001234567",
            "+923105551234",
            "+923001234567",  # Duplicate
            "+923215678901",
            "+923105551234",  # Duplicate
        ]
        
        duplicates = PhoneValidator.detect_duplicates(phones)
        self.assertEqual(len(duplicates), 2)


class TestDataValidator(unittest.TestCase):
    """Test data validation functionality."""
    
    def test_valid_email(self):
        """Test email validation."""
        valid_emails = [
            "test@example.com",
            "user.name@company.co.uk",
            "admin+tag@domain.org",
        ]
        
        for email in valid_emails:
            self.assertTrue(
                DataValidator.is_valid_email(email),
                f"Should be valid: {email}"
            )
    
    def test_invalid_email(self):
        """Test invalid email formats."""
        invalid_emails = [
            "notanemail",
            "test@",
            "@example.com",
            "test @example.com",
        ]
        
        for email in invalid_emails:
            self.assertFalse(
                DataValidator.is_valid_email(email),
                f"Should be invalid: {email}"
            )
    
    def test_message_length(self):
        """Test message length validation."""
        short_msg = "This is a short message"
        long_msg = "x" * 2500
        very_long_msg = "x" * 70000
        
        # Short message
        is_valid, _ = DataValidator.validate_message_length(short_msg)
        self.assertTrue(is_valid)
        
        # Long message (warning but valid)
        is_valid, warning = DataValidator.validate_message_length(long_msg)
        self.assertTrue(is_valid)
        self.assertTrue(len(warning) > 0)
        
        # Too long message
        is_valid, _ = DataValidator.validate_message_length(very_long_msg)
        self.assertFalse(is_valid)


class TestContactModel(unittest.TestCase):
    """Test Contact model."""
    
    def test_contact_creation(self):
        """Test contact creation."""
        contact = Contact(
            phone="+923001234567",
            name="Ahmed Khan",
            tags=["VIP", "Premium"]
        )
        
        self.assertEqual(contact.phone, "+923001234567")
        self.assertEqual(contact.name, "Ahmed Khan")
        self.assertEqual(len(contact.tags), 2)
    
    def test_contact_to_dict(self):
        """Test converting contact to dictionary."""
        contact = Contact(
            phone="+923001234567",
            name="Ahmed Khan",
            tags=["VIP"]
        )
        
        data = contact.to_dict()
        
        self.assertIn('phone', data)
        self.assertIn('name', data)
        self.assertIn('tags', data)
        self.assertEqual(data['phone'], "+923001234567")


class TestCampaignModel(unittest.TestCase):
    """Test Campaign model."""
    
    def test_campaign_creation(self):
        """Test campaign creation."""
        campaign = Campaign(
            name="Fee Reminder",
            message_template="Dear {name}, your fee is due",
            total_contacts=100
        )
        
        self.assertEqual(campaign.name, "Fee Reminder")
        self.assertEqual(campaign.total_contacts, 100)
        self.assertEqual(campaign.sent_count, 0)


class TestTemplateModel(unittest.TestCase):
    """Test Template model."""
    
    def test_template_creation(self):
        """Test template creation."""
        template = Template(
            name="Fee Reminder",
            category="Education",
            message_text="Dear {name}, your fee is due on {due_date}"
        )
        
        self.assertEqual(template.name, "Fee Reminder")
        self.assertEqual(template.category, "Education")
        self.assertTrue("{name}" in template.message_text)


class TestLicenseManager(unittest.TestCase):
    """Test trial and paid license behavior."""

    def test_paid_passkey_validation(self):
        """Only the configured passkey should activate the paid license."""
        self.assertTrue(LicenseManager._verify_license_key(PAID_PASSKEY))
        self.assertFalse(LicenseManager._verify_license_key("wrong-key"))

    def test_trial_duration_enforced_to_three_days(self):
        """Stored trial files should respect the current 3-day product policy."""
        with tempfile.TemporaryDirectory() as temp_dir:
            license_path = Path(temp_dir) / "license.lic"
            old_trial = {
                "type": "trial",
                "trial_start": "2026-05-01T10:00:00",
                "trial_end": "2026-05-15T10:00:00",
                "license_key": None,
            }
            license_path.write_text(json.dumps(old_trial), encoding="utf-8")

            with patch.object(LicenseManager, "get_license_path", return_value=license_path), \
                 patch("utils.license_manager.datetime") as mocked_datetime:
                mocked_datetime.now.return_value = datetime.fromisoformat("2026-05-03T09:00:00")
                mocked_datetime.fromisoformat.side_effect = lambda value: datetime.fromisoformat(value)
                status = LicenseManager.check_license()

            self.assertEqual(status["status"], "trial")
            self.assertTrue(status["is_valid"])
            self.assertLessEqual(status["days_remaining"], TRIAL_DAYS)


if __name__ == "__main__":
    unittest.main()

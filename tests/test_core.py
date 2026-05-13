"""
Unit tests for MessageCannon application.
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils.validators import PhoneValidator, DataValidator
from models import Contact, Campaign, Template


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


if __name__ == "__main__":
    unittest.main()

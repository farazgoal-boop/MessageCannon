"""
Validators module for phone numbers, emails, and data validation.
"""

import re
from typing import Tuple, Optional
from .constants import PAKISTAN_PHONE_PATTERN


class PhoneValidator:
    """Validates and formats phone numbers."""
    
    @staticmethod
    def is_valid_pakistan_format(phone: str) -> bool:
        """
        Validate Pakistan phone number format (+92xxxxxxxxxx).
        
        Args:
            phone: Phone number string
            
        Returns:
            True if valid Pakistan format, False otherwise
        """
        return bool(re.match(PAKISTAN_PHONE_PATTERN, phone))
    
    @staticmethod
    def is_valid_international_format(phone: str) -> bool:
        """
        Validate international phone number format.
        
        Args:
            phone: Phone number string
            
        Returns:
            True if valid international format, False otherwise
        """
        pattern = r"^\+\d{1,3}\d{6,14}$"
        return bool(re.match(pattern, phone))
    
    @staticmethod
    def normalize_phone(phone: str) -> Tuple[Optional[str], str]:
        """
        Normalize phone number to standard format.
        Auto-correct common formatting issues.
        
        Args:
            phone: Raw phone number string
            
        Returns:
            Tuple of (normalized_phone, error_message)
            Returns (None, error_message) if invalid
        """
        if not phone:
            return None, "Phone number cannot be empty"
        
        # Remove common characters
        phone = phone.strip()
        phone = re.sub(r'[\s\-\(\)]+', '', phone)
        
        # Handle leading 0 for Pakistan numbers
        if phone.startswith('0') and len(phone) == 11:
            phone = '+92' + phone[1:]
        
        # Add +92 if it's just the digits
        if re.match(r"^92\d{10}$", phone):
            phone = '+' + phone
        
        # Validate
        if PhoneValidator.is_valid_pakistan_format(phone):
            return phone, ""
        elif PhoneValidator.is_valid_international_format(phone):
            return phone, ""
        else:
            return None, PhoneValidator._describe_phone_error(phone)

    @staticmethod
    def _describe_phone_error(phone: str) -> str:
        """Best-effort specific reason a normalized phone still failed
        validation — used by import review UIs so users see *why*, not just
        a generic rejection."""
        digits_only = re.sub(r"\D", "", phone)
        if not digits_only:
            return "Contains no digits"
        if not phone.startswith("+"):
            return "Missing country code (e.g. +1, +92)"
        if len(digits_only) < 7:
            return "Number too short"
        if len(digits_only) > 15:
            return "Number too long"
        if not re.match(r"^\+\d+$", phone):
            return "Contains invalid characters"
        return f"Invalid phone number format: {phone}"
    
    @staticmethod
    def detect_duplicates(phones: list) -> list:
        """
        Detect duplicate phone numbers.
        
        Args:
            phones: List of phone numbers
            
        Returns:
            List of duplicate phone numbers
        """
        seen = set()
        duplicates = set()
        
        for phone in phones:
            if phone in seen:
                duplicates.add(phone)
            seen.add(phone)
        
        return list(duplicates)


class DataValidator:
    """Validates data formats and content."""
    
    @staticmethod
    def is_valid_email(email: str) -> bool:
        """
        Validate email address.
        
        Args:
            email: Email string
            
        Returns:
            True if valid email, False otherwise
        """
        pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return bool(re.match(pattern, email))
    
    @staticmethod
    def is_valid_csv_headers(headers: list, required_fields: list) -> Tuple[bool, str]:
        """
        Validate CSV/Excel headers contain required fields.
        
        Args:
            headers: List of column headers
            required_fields: List of required field names
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        headers_lower = [h.lower().strip() for h in headers]
        
        missing = []
        for field in required_fields:
            if field.lower() not in headers_lower:
                missing.append(field)
        
        if missing:
            return False, f"Missing required columns: {', '.join(missing)}"
        
        return True, ""
    
    @staticmethod
    def validate_message_length(message: str, max_length: int = 65536) -> Tuple[bool, str]:
        """
        Validate message length.
        
        Args:
            message: Message text
            max_length: Maximum allowed length (WhatsApp limit: 65536)
            
        Returns:
            Tuple of (is_valid, warning_message)
        """
        length = len(message)
        
        if length > max_length:
            return False, f"Message exceeds WhatsApp limit ({length}/{max_length})"
        
        if length > 2000:
            return True, f"Message is quite long ({length} chars). May be split into multiple messages."
        
        return True, ""
    
    @staticmethod
    def validate_template_variables(message: str, available_vars: list) -> Tuple[bool, list]:
        """
        Validate that all variables in message are available.
        
        Args:
            message: Message text with variables
            available_vars: List of available variables
            
        Returns:
            Tuple of (is_valid, list_of_invalid_vars)
        """
        # Find all variables in format {var_name}
        pattern = r"\{([^}]+)\}"
        found_vars = re.findall(pattern, message)
        
        invalid_vars = []
        for var in found_vars:
            if f"{{{var}}}" not in available_vars:
                invalid_vars.append(var)
        
        is_valid = len(invalid_vars) == 0
        return is_valid, invalid_vars

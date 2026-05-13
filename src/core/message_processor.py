"""
Message processor for handling message templates and variable substitution.
"""

import re
from typing import List, Dict, Tuple, Optional
from datetime import datetime

from ..models import Contact, MessageLog, MessageStatus
from ..utils.validators import DataValidator
from ..utils.logger import Logger


class MessageProcessor:
    """Processes messages and handles variable substitution."""
    
    # Message variable pattern
    VAR_PATTERN = r"\{([^}]+)\}"
    
    def __init__(self):
        """Initialize message processor."""
        pass
    
    def substitute_variables(self, template: str, contact: Contact) -> Tuple[str, bool]:
        """
        Substitute variables in message template for a specific contact.
        
        Args:
            template: Message template with variables like {name}, {amount}
            contact: Contact object with data
            
        Returns:
            Tuple of (processed_message, success_flag)
        """
        try:
            message = template
            
            # Find all variables
            variables = re.findall(self.VAR_PATTERN, message)
            
            for var in variables:
                placeholder = f"{{{var}}}"
                value = self._get_variable_value(var, contact)
                
                if value is None:
                    Logger.warning(f"Variable {var} not found for contact {contact.phone}")
                    value = ""
                
                message = message.replace(placeholder, str(value))
            
            return message, True
        
        except Exception as e:
            Logger.error(f"Error substituting variables: {e}")
            return template, False
    
    @staticmethod
    def _get_variable_value(var_name: str, contact: Contact) -> Optional[str]:
        """
        Get variable value from contact data.
        
        Args:
            var_name: Variable name
            contact: Contact object
            
        Returns:
            Variable value or None
        """
        var_name_lower = var_name.lower()
        
        # Check standard fields
        if var_name_lower == 'phone':
            return contact.phone
        elif var_name_lower == 'name':
            return contact.name
        
        # Check custom fields
        if var_name in contact.custom_fields:
            return contact.custom_fields[var_name]
        
        # Check with lowercased keys
        for key, value in contact.custom_fields.items():
            if key.lower() == var_name_lower:
                return value
        
        return None
    
    def validate_template(self, template: str) -> Tuple[bool, List[str]]:
        """
        Validate message template.
        
        Args:
            template: Message template
            
        Returns:
            Tuple of (is_valid, list_of_warnings)
        """
        warnings = []
        
        # Check length
        is_valid, length_msg = DataValidator.validate_message_length(template)
        if not is_valid:
            return False, [length_msg]
        
        if length_msg:
            warnings.append(length_msg)
        
        # Find variables
        variables = re.findall(self.VAR_PATTERN, template)
        
        if len(variables) != len(set(variables)):
            duplicate_vars = [v for v in set(variables) 
                             if variables.count(v) > 1]
            warnings.append(f"Duplicate variables: {', '.join(duplicate_vars)}")
        
        return True, warnings
    
    def process_batch(self, template: str, contacts: List[Contact]) -> List[MessageLog]:
        """
        Process message template for batch of contacts.
        
        Args:
            template: Message template
            contacts: List of contacts
            
        Returns:
            List of MessageLog objects
        """
        logs = []
        
        for contact in contacts:
            message, success = self.substitute_variables(template, contact)
            
            if not success:
                log = MessageLog(
                    contact_phone=contact.phone,
                    contact_name=contact.name,
                    message_text=template,
                    status=MessageStatus.FAILED,
                    error_message="Failed to process message"
                )
            else:
                log = MessageLog(
                    contact_phone=contact.phone,
                    contact_name=contact.name,
                    message_text=message,
                    status=MessageStatus.PENDING
                )
            
            logs.append(log)
        
        return logs
    
    def get_template_variables(self, template: str) -> List[str]:
        """
        Extract all variables from template.
        
        Args:
            template: Message template
            
        Returns:
            List of unique variable names
        """
        variables = re.findall(self.VAR_PATTERN, template)
        return list(set(variables))
    
    def split_long_message(self, message: str, max_length: int = 1000) -> List[str]:
        """
        Split long message into parts (if needed for WhatsApp).
        
        Args:
            message: Message text
            max_length: Maximum length per part
            
        Returns:
            List of message parts
        """
        if len(message) <= max_length:
            return [message]
        
        parts = []
        words = message.split(' ')
        current_part = ""
        
        for word in words:
            if len(current_part) + len(word) + 1 > max_length:
                if current_part:
                    parts.append(current_part.strip())
                current_part = word
            else:
                current_part += f" {word}"
        
        if current_part:
            parts.append(current_part.strip())
        
        return parts

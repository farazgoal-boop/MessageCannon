"""
Contact manager for handling contact operations.
"""

import pandas as pd
from pathlib import Path
from typing import List, Tuple, Optional
import io

from ..models import Contact
from ..database.db_manager import DatabaseManager
from ..utils.validators import PhoneValidator, DataValidator
from ..utils.logger import Logger


class ContactManager:
    """Manages contact import, validation, and operations."""
    
    def __init__(self):
        """Initialize contact manager."""
        self.db = DatabaseManager()
        self.phone_validator = PhoneValidator()
    
    def import_from_file(self, file_path: str) -> Tuple[int, List[str]]:
        """
        Import contacts from Excel or CSV file.
        
        Args:
            file_path: Path to Excel or CSV file
            
        Returns:
            Tuple of (count_imported, list_of_errors)
        """
        try:
            file_path = Path(file_path)
            
            if not file_path.exists():
                return 0, [f"File not found: {file_path}"]
            
            # Read file based on extension
            if file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            elif file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            else:
                return 0, [f"Unsupported file format: {file_path.suffix}"]
            
            # Validate headers
            required_fields = ['phone']
            valid, error = DataValidator.is_valid_csv_headers(df.columns.tolist(), required_fields)
            if not valid:
                return 0, [error]
            
            # Process rows
            contacts = []
            errors = []
            
            for idx, row in df.iterrows():
                phone = str(row.get('phone', '')).strip()
                name = str(row.get('name', '')).strip()
                
                # Normalize phone
                normalized_phone, phone_error = self.phone_validator.normalize_phone(phone)
                
                if normalized_phone is None:
                    errors.append(f"Row {idx + 2}: {phone_error}")
                    continue
                
                # Create contact
                contact = Contact(
                    phone=normalized_phone,
                    name=name or f"Contact {idx + 1}",
                    custom_fields={k: v for k, v in row.to_dict().items() 
                                   if k.lower() not in ['phone', 'name']}
                )
                
                contacts.append(contact)
            
            # Batch add to database
            count = self.db.add_contacts_batch(contacts)
            
            Logger.info(f"Imported {count} contacts from {file_path}")
            
            return count, errors
        
        except Exception as e:
            Logger.error(f"Error importing contacts: {e}")
            return 0, [str(e)]
    
    def get_all_contacts(self) -> List[Contact]:
        """
        Get all contacts.
        
        Returns:
            List of Contact objects
        """
        return self.db.get_contacts()
    
    def get_contacts_paginated(self, page: int = 1, page_size: int = 50) -> List[Contact]:
        """
        Get contacts with pagination.
        
        Args:
            page: Page number (1-indexed)
            page_size: Number of contacts per page
            
        Returns:
            List of Contact objects
        """
        offset = (page - 1) * page_size
        return self.db.get_contacts(limit=page_size, offset=offset)
    
    def get_contact_count(self) -> int:
        """
        Get total number of contacts.
        
        Returns:
            Contact count
        """
        return self.db.get_contact_count()
    
    def search_contacts(self, query: str) -> List[Contact]:
        """
        Search contacts by name or phone.
        
        Args:
            query: Search query
            
        Returns:
            List of matching Contact objects
        """
        return self.db.search_contacts(query)
    
    def delete_contact(self, contact_id: int) -> bool:
        """
        Delete contact by ID.
        
        Args:
            contact_id: Contact ID
            
        Returns:
            True if successful, False otherwise
        """
        return self.db.delete_contact(contact_id)
    
    def get_preview_data(self, contacts: List[Contact], max_rows: int = 20) -> Tuple[List[dict], int]:
        """
        Get preview data for contact import.
        
        Args:
            contacts: List of contacts
            max_rows: Maximum rows to show
            
        Returns:
            Tuple of (preview_list, total_count)
        """
        preview = []
        
        for i, contact in enumerate(contacts[:max_rows]):
            preview.append({
                'id': i + 1,
                'phone': contact.phone,
                'name': contact.name,
                'tags': ', '.join(contact.tags) if contact.tags else ''
            })
        
        return preview, len(contacts)
    
    def export_contacts(self, output_file: str, contacts: Optional[List[Contact]] = None) -> bool:
        """
        Export contacts to CSV.
        
        Args:
            output_file: Output CSV file path
            contacts: Contacts to export (if None, export all)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if contacts is None:
                contacts = self.get_all_contacts()
            
            data = []
            for contact in contacts:
                data.append({
                    'phone': contact.phone,
                    'name': contact.name,
                    'tags': ', '.join(contact.tags),
                    **contact.custom_fields
                })
            
            df = pd.DataFrame(data)
            df.to_csv(output_file, index=False, encoding='utf-8')
            
            Logger.info(f"Exported {len(contacts)} contacts to {output_file}")
            return True
        
        except Exception as e:
            Logger.error(f"Error exporting contacts: {e}")
            return False
    
    def detect_issues(self, contacts: List[Contact]) -> dict:
        """
        Detect data quality issues in contacts.
        
        Args:
            contacts: List of contacts
            
        Returns:
            Dictionary of issues
        """
        issues = {
            'duplicate_phones': [],
            'invalid_phones': [],
            'missing_names': [],
        }
        
        phones = [c.phone for c in contacts]
        duplicates = PhoneValidator.detect_duplicates(phones)
        issues['duplicate_phones'] = duplicates
        
        for contact in contacts:
            if not contact.name or contact.name.strip() == '':
                issues['missing_names'].append(contact.phone)
        
        return issues

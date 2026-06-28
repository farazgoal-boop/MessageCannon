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
        Import contacts from CSV, Excel, HTML, JSON, or VCF files.

        Args:
            file_path: Path to import file

        Returns:
            Tuple of (count_imported, list_of_errors)
        """
        try:
            from ..modules.data_importer import UniversalDataImporter

            result = UniversalDataImporter().import_file(file_path)
            if result.errors and not result.contacts:
                return 0, result.errors

            contacts: List[Contact] = []
            errors = list(result.errors)

            for row in result.contacts:
                phone_raw = row.get("phone", "")
                email_raw = row.get("email", "")
                name = row.get("name", "")

                normalized_phone = ""
                if phone_raw:
                    normalized_phone, phone_error = self.phone_validator.normalize_phone(phone_raw)
                    if normalized_phone is None and not email_raw:
                        errors.append(f"{name or phone_raw}: {phone_error}")
                        continue
                    normalized_phone = normalized_phone or ""

                if email_raw and not DataValidator.is_valid_email(email_raw):
                    if not normalized_phone:
                        errors.append(f"{name or email_raw}: Invalid email")
                        continue
                    email_raw = ""

                if not normalized_phone and not email_raw:
                    continue

                custom_fields = {
                    key[7:]: value
                    for key, value in row.items()
                    if key.startswith("custom_") and value
                }

                contacts.append(
                    Contact(
                        phone=normalized_phone or None,
                        email=email_raw or None,
                        name=name or None,
                        custom_fields=custom_fields or None,
                    )
                )

            if not contacts:
                return 0, errors or ["No valid contacts found in file."]

            saved = self.db.add_contacts_batch(contacts)
            Logger.info(f"Imported {saved} contacts from {file_path}")
            return saved, errors

        except Exception as exc:
            Logger.error(f"Import failed: {exc}")
            return 0, [str(exc)]

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
                'email': contact.email,
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
                    'email': contact.email,
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

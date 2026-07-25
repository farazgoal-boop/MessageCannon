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
    
    def analyze_import(self, file_path: str) -> dict:
        """Parse and classify every row from file_path WITHOUT writing to the
        DB — powers the import review UI. Each row dict: {index, name, phone,
        email, custom_fields, status, channel, reason} where status is one
        of "valid", "invalid", "dup_in_file", "dup_in_db", and channel (only
        meaningful when status != "invalid") is one of "whatsapp", "email",
        "both" — which campaign channel(s) this contact is eligible for.

        A contact needs a usable phone OR a usable email, not necessarily
        both — `contacts.phone` is nullable (see
        `DatabaseManager._migrate_contacts_phone_nullable`, which rebuilds
        any older on-disk table that still had a NOT NULL constraint on
        phone, the real reason email-only contacts used to be rejected
        outright). Only a row with *neither* a usable phone nor a usable
        email is genuinely "invalid".

        Duplicate detection keys off phone when the row has one (phone is
        the more stable identity — a WhatsApp number), and falls back to
        email (case-insensitively) for phone-less rows.
        """
        from ..modules.data_importer import UniversalDataImporter

        result = UniversalDataImporter().import_file(file_path)
        if result.errors and not result.contacts:
            return {"rows": [], "columns_found": result.columns_found, "parse_errors": result.errors}

        existing_phones = self.db.get_existing_phones()
        existing_emails = self.db.get_existing_emails()
        seen_phones_in_file: dict = {}
        seen_emails_in_file: dict = {}
        rows: List[dict] = []

        for i, raw_row in enumerate(result.contacts):
            name = str(raw_row.get("name", "")).strip()
            phone_raw = str(raw_row.get("phone", "")).strip()
            email_raw = str(raw_row.get("email", "")).strip()
            custom_fields = {
                key[7:]: value for key, value in raw_row.items()
                if key.startswith("custom_") and value
            }

            normalized_phone, phone_error = (
                self.phone_validator.normalize_phone(phone_raw) if phone_raw else (None, ""))
            email_valid = DataValidator.is_valid_email(email_raw) if email_raw else False
            email_clean = email_raw if email_valid else ""
            has_phone = bool(normalized_phone)
            has_email = bool(email_clean)

            row = {
                "index": i, "name": name,
                "phone": normalized_phone or "", "raw_phone": phone_raw,
                "email": email_clean, "raw_email": email_raw,
                "custom_fields": custom_fields,
                "status": "valid", "channel": "", "reason": "", "warning": "",
            }

            if not has_phone and not has_email:
                reasons = []
                if phone_raw:
                    reasons.append(f"Phone: {phone_error}")
                if email_raw and not email_valid:
                    reasons.append("Invalid email format")
                if not reasons:
                    reasons.append("No phone number or email address")
                row["status"] = "invalid"
                row["reason"] = "; ".join(reasons)
                rows.append(row)
                continue

            row["channel"] = "both" if (has_phone and has_email) else ("whatsapp" if has_phone else "email")
            if email_raw and not email_valid and has_phone:
                row["warning"] = "Email dropped — invalid format (row still valid for WhatsApp)"

            if has_phone:
                if normalized_phone in existing_phones:
                    row["status"] = "dup_in_db"
                    row["reason"] = "Phone already exists in your contacts"
                elif normalized_phone in seen_phones_in_file:
                    row["status"] = "dup_in_file"
                    row["reason"] = f"Duplicate of row {seen_phones_in_file[normalized_phone] + 1} in this file"
                else:
                    seen_phones_in_file[normalized_phone] = i
            else:
                email_key = email_clean.lower()
                if email_key in existing_emails:
                    row["status"] = "dup_in_db"
                    row["reason"] = "Email already exists in your contacts"
                elif email_key in seen_emails_in_file:
                    row["status"] = "dup_in_file"
                    row["reason"] = f"Duplicate of row {seen_emails_in_file[email_key] + 1} in this file"
                else:
                    seen_emails_in_file[email_key] = i

            rows.append(row)

        return {"rows": rows, "columns_found": result.columns_found, "parse_errors": result.errors}

    def commit_import(self, rows: List[dict], dup_resolution: str = "skip") -> dict:
        """Write reviewed rows to the DB. Only rows with status "valid" are
        inserted as new contacts; rows with status "dup_in_db"/"dup_in_file"
        are either skipped entirely (dup_resolution="skip") or merged into
        the existing DB row (dup_resolution="merge") — merging only fills in
        blank fields, never overwrites existing data with blanks. Rows with
        status "invalid" are always skipped. Returns
        {"imported": int, "merged": int, "skipped_duplicates": int, "skipped_invalid": int}.
        """
        imported = merged = skipped_duplicates = skipped_invalid = 0
        to_insert: List[Contact] = []

        for row in rows:
            status = row["status"]
            if status == "invalid":
                skipped_invalid += 1
                continue
            # analyze_import only reaches "valid"/"dup_*" when the row has a
            # usable phone and/or email — never neither (see its docstring).
            # Duplicate matching keys off phone when the row has one, else
            # email, mirroring analyze_import's own duplicate-detection key.
            if status in ("dup_in_db", "dup_in_file"):
                if dup_resolution == "merge":
                    if row["phone"]:
                        merged_ok = self.db.update_contact_by_phone(
                            row["phone"], name=row["name"], email=row["email"],
                            custom_fields=row["custom_fields"])
                    else:
                        merged_ok = self.db.update_contact_by_email(
                            row["email"], name=row["name"], phone=row["phone"],
                            custom_fields=row["custom_fields"])
                    if merged_ok:
                        merged += 1
                    else:
                        skipped_duplicates += 1
                else:
                    skipped_duplicates += 1
                continue
            to_insert.append(Contact(
                phone=row["phone"] or None, email=row["email"] or "", name=row["name"] or "",
                custom_fields=row["custom_fields"] or {},
            ))

        if to_insert:
            imported = self.db.add_contacts_batch(to_insert)
            skipped_duplicates += len(to_insert) - imported  # lost a race to a concurrent insert

        return {
            "imported": imported, "merged": merged,
            "skipped_duplicates": skipped_duplicates, "skipped_invalid": skipped_invalid,
        }

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

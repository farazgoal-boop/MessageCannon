"""
MessageCannon Pro - Universal Data Importer
Supports: CSV, XLS, XLSX, XLSM, HTML, HTM, JSON, VCF (vCard)
"""

from __future__ import annotations

import csv
import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ImportResult:
    """Result container for a contact import operation."""

    def __init__(self) -> None:
        self.contacts: List[Dict[str, str]] = []
        self.total: int = 0
        self.skipped: int = 0
        self.valid_emails: int = 0
        self.valid_phones: int = 0
        self.errors: List[str] = []
        self.source_type: str = ""
        self.columns_found: List[str] = []

    def summary(self) -> str:
        """Human-readable import summary."""
        return (
            f"Imported {self.total} contacts from {self.source_type}\n"
            f"Valid emails: {self.valid_emails} | Valid phones: {self.valid_phones}\n"
            f"Skipped: {self.skipped} | Errors: {len(self.errors)}"
        )


class UniversalDataImporter:
    """
    One-stop importer for CSV, Excel, HTML, JSON, and VCF files.
    Auto-detects column names (name, email, phone, etc.).
    """

    NAME_COLS = [
        "name", "full name", "fullname", "customer", "client",
        "contact", "person", "fname", "first name", "recipient", "fn",
    ]
    EMAIL_COLS = ["email", "e-mail", "email address", "mail", "e mail"]
    PHONE_COLS = [
        "phone", "mobile", "cell", "whatsapp", "number",
        "contact number", "phone number", "tel", "telephone",
    ]

    SUPPORTED_EXTENSIONS = {
        ".csv", ".xls", ".xlsx", ".xlsm",
        ".html", ".htm", ".json", ".vcf",
    }

    def import_file(self, filepath: str, sheet_index: int = 0) -> ImportResult:
        """Auto-detect file type and import contacts."""
        path = Path(filepath)
        ext = path.suffix.lower()
        result = ImportResult()

        if ext not in self.SUPPORTED_EXTENSIONS:
            result.errors.append(f"Unsupported file type: {ext}")
            return result

        try:
            if ext == ".csv":
                result.source_type = "CSV"
                self._import_csv(filepath, result)
            elif ext == ".xls":
                result.source_type = "Excel (.xls)"
                self._import_xls(filepath, result, sheet_index)
            elif ext in (".xlsx", ".xlsm"):
                result.source_type = f"Excel ({ext})"
                self._import_xlsx(filepath, result, sheet_index)
            elif ext in (".html", ".htm"):
                result.source_type = "HTML"
                self._import_html(filepath, result)
            elif ext == ".json":
                result.source_type = "JSON"
                self._import_json(filepath, result)
            elif ext == ".vcf":
                result.source_type = "VCF (vCard)"
                self._import_vcf(filepath, result)
        except Exception as exc:
            logger.exception("Import failed for %s", filepath)
            result.errors.append(str(exc))

        self._finalize_stats(result)
        return result

    def _finalize_stats(self, result: ImportResult) -> None:
        """Compute valid email/phone counts after import — real validation,
        not just "field is non-empty" (values now pass through _clean_email/
        _clean_phone unjudged, so presence alone no longer implies validity)."""
        from ..utils.validators import DataValidator, PhoneValidator
        phone_validator = PhoneValidator()
        result.valid_emails = sum(
            1 for c in result.contacts if c.get("email") and DataValidator.is_valid_email(c["email"]))
        result.valid_phones = sum(
            1 for c in result.contacts
            if c.get("phone") and phone_validator.normalize_phone(c["phone"])[0])

    def _import_csv(self, filepath: str, result: ImportResult) -> None:
        try:
            with open(filepath, newline="", encoding="utf-8-sig") as handle:
                sample = handle.read(4096)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except Exception:
            dialect = csv.excel

        with open(filepath, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle, dialect=dialect)
            col_map = self._map_columns(reader.fieldnames or [])
            result.columns_found = list(reader.fieldnames or [])
            for row in reader:
                contact = self._extract_contact(row, col_map)
                if contact:
                    result.contacts.append(contact)
                    result.total += 1
                else:
                    result.skipped += 1

    def _import_xls(self, filepath: str, result: ImportResult, sheet_index: int) -> None:
        try:
            import xlrd
        except ImportError:
            result.errors.append("xlrd not installed. Run: pip install xlrd")
            return

        book = xlrd.open_workbook(filepath)
        sheet = book.sheet_by_index(sheet_index)
        if sheet.nrows < 1:
            result.errors.append("Excel sheet is empty.")
            return

        headers = [str(sheet.cell_value(0, col)).strip() for col in range(sheet.ncols)]
        result.columns_found = headers
        col_map = self._map_columns(headers)

        for row_idx in range(1, sheet.nrows):
            row = {
                headers[col]: str(sheet.cell_value(row_idx, col)).strip()
                for col in range(sheet.ncols)
                if headers[col]
            }
            contact = self._extract_contact(row, col_map)
            if contact:
                result.contacts.append(contact)
                result.total += 1
            else:
                result.skipped += 1

    def _import_xlsx(self, filepath: str, result: ImportResult, sheet_index: int) -> None:
        try:
            import openpyxl
        except ImportError:
            result.errors.append("openpyxl not installed. Run: pip install openpyxl")
            return

        workbook = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        sheet = workbook.worksheets[sheet_index]
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            result.errors.append("Excel sheet is empty.")
            return

        headers = [str(cell).strip() if cell is not None else "" for cell in rows[0]]
        result.columns_found = headers
        col_map = self._map_columns(headers)

        for raw_row in rows[1:]:
            row = {
                headers[index]: (str(raw_row[index]).strip() if raw_row[index] is not None else "")
                for index in range(len(headers))
            }
            contact = self._extract_contact(row, col_map)
            if contact:
                result.contacts.append(contact)
                result.total += 1
            else:
                result.skipped += 1

    def _import_html(self, filepath: str, result: ImportResult) -> None:
        with open(filepath, encoding="utf-8-sig", errors="replace") as handle:
            content = handle.read()

        tables = self._parse_html_tables(content)
        if not tables:
            result.errors.append("No <table> elements found in HTML file.")
            return

        table = max(tables, key=len)
        if len(table) < 2:
            result.errors.append("HTML table has fewer than 2 rows.")
            return

        headers = [str(cell).strip() for cell in table[0]]
        result.columns_found = headers
        col_map = self._map_columns(headers)

        for raw_row in table[1:]:
            row = {
                headers[index]: str(raw_row[index]).strip()
                for index in range(min(len(headers), len(raw_row)))
            }
            contact = self._extract_contact(row, col_map)
            if contact:
                result.contacts.append(contact)
                result.total += 1
            else:
                result.skipped += 1

    def _import_json(self, filepath: str, result: ImportResult) -> None:
        with open(filepath, encoding="utf-8-sig") as handle:
            payload = json.load(handle)

        records: List[Any]
        if isinstance(payload, list):
            records = payload
        elif isinstance(payload, dict):
            for key in ("contacts", "data", "records", "items", "rows"):
                if isinstance(payload.get(key), list):
                    records = payload[key]
                    break
            else:
                records = [payload]
        else:
            result.errors.append("JSON must be an array or object with a contacts list.")
            return

        if not records:
            result.errors.append("JSON contains no contact records.")
            return

        if isinstance(records[0], dict):
            headers = list(records[0].keys())
            result.columns_found = headers
            col_map = self._map_columns(headers)
            for record in records:
                if not isinstance(record, dict):
                    result.skipped += 1
                    continue
                row = {str(k): str(v).strip() if v is not None else "" for k, v in record.items()}
                contact = self._extract_contact(row, col_map)
                if contact:
                    result.contacts.append(contact)
                    result.total += 1
                else:
                    result.skipped += 1
        else:
            result.errors.append("JSON records must be objects with contact fields.")

    def _import_vcf(self, filepath: str, result: ImportResult) -> None:
        with open(filepath, encoding="utf-8-sig", errors="replace") as handle:
            content = handle.read()

        cards = re.split(r"BEGIN:VCARD", content, flags=re.IGNORECASE)
        result.columns_found = ["name", "email", "phone"]

        for card in cards:
            if not card.strip():
                continue
            name = self._vcf_field(card, "FN") or self._vcf_field(card, "N")
            email = self._vcf_field(card, "EMAIL")
            phone = self._vcf_field(card, "TEL")
            if not any([name, email, phone]):
                result.skipped += 1
                continue
            contact = {
                "name": name.strip(),
                "email": self._clean_email(email),
                "phone": self._clean_phone(phone),
            }
            result.contacts.append(contact)
            result.total += 1

    @staticmethod
    def _vcf_field(card: str, field: str) -> str:
        pattern = rf"^{field}[;:](.+)$"
        for line in card.splitlines():
            match = re.match(pattern, line.strip(), re.IGNORECASE)
            if match:
                return match.group(1).split(":", 1)[-1].strip()
        return ""

    def _parse_html_tables(self, html: str) -> List[List[List[str]]]:
        """Minimal HTML table parser — no external deps."""
        tables: List[List[List[str]]] = []
        for table_html in re.findall(
            r"<table[^>]*>(.*?)</table>", html, re.DOTALL | re.IGNORECASE
        ):
            rows: List[List[str]] = []
            for row_html in re.findall(
                r"<tr[^>]*>(.*?)</tr>", table_html, re.DOTALL | re.IGNORECASE
            ):
                cells = re.findall(
                    r"<t[hd][^>]*>(.*?)</t[hd]>", row_html, re.DOTALL | re.IGNORECASE
                )
                clean = [re.sub(r"<[^>]+>", "", cell).strip() for cell in cells]
                if any(clean):
                    rows.append(clean)
            if rows:
                tables.append(rows)
        return tables

    def _map_columns(self, headers: List[str]) -> Dict[str, str]:
        """Map logical fields to actual column names."""
        mapping: Dict[str, str] = {}
        lower_headers = {header.lower().strip(): header for header in headers if header}

        for alias in self.NAME_COLS:
            if alias in lower_headers and "name" not in mapping:
                mapping["name"] = lower_headers[alias]

        for alias in self.EMAIL_COLS:
            if alias in lower_headers and "email" not in mapping:
                mapping["email"] = lower_headers[alias]

        for alias in self.PHONE_COLS:
            if alias in lower_headers and "phone" not in mapping:
                mapping["phone"] = lower_headers[alias]

        return mapping

    def _extract_contact(self, row: Dict[str, str], col_map: Dict[str, str]) -> Optional[Dict[str, str]]:
        """Extract a contact dict; returns None if no usable data."""
        name = row.get(col_map.get("name", ""), "").strip()
        email = row.get(col_map.get("email", ""), "").strip()
        phone = row.get(col_map.get("phone", ""), "").strip()

        if not any([name, email, phone]):
            return None

        contact: Dict[str, str] = {
            "name": name,
            "email": self._clean_email(email),
            "phone": self._clean_phone(phone),
        }

        for key, value in row.items():
            if key and key not in col_map.values():
                contact[f"custom_{key}"] = str(value).strip()

        return contact

    @staticmethod
    def _clean_email(email: str) -> str:
        # Trim/lowercase only — do NOT silently discard malformed values here.
        # Real validation (with a specific reason) is DataValidator's job;
        # nulling out bad-looking input at this layer would destroy the very
        # information callers need to explain *why* a row was rejected.
        return email.strip().lower()

    @staticmethod
    def _clean_phone(phone: str) -> str:
        # Strip formatting characters only — do NOT discard short/malformed
        # values. Real validation (with a specific reason) is PhoneValidator's
        # job; see _clean_email for why this layer must not pre-judge.
        return re.sub(r"[^\d+]", "", phone)

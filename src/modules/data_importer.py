"""
MessageCannon Pro - Universal Data Importer
Supports: CSV, XLS, XLSX, HTML (table scraping)
"""

import csv
import io
import os
import re
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class ImportResult:
    def __init__(self):
        self.contacts = []        # list of dicts: {name, email, phone, ...}
        self.total = 0
        self.skipped = 0
        self.errors = []
        self.source_type = ""
        self.columns_found = []

    def summary(self):
        return (
            f"Imported {self.total} contacts from {self.source_type}\n"
            f"Skipped: {self.skipped} | Errors: {len(self.errors)}"
        )


class UniversalDataImporter:
    """
    One-stop importer for CSV, XLS/XLSX, and HTML files.
    Auto-detects column names (name, email, phone, etc.)
    """

    # Common column aliases we auto-map
    NAME_COLS   = ["name", "full name", "fullname", "customer", "client",
                   "contact", "person", "fname", "first name", "recipient"]
    EMAIL_COLS  = ["email", "e-mail", "email address", "mail", "e mail"]
    PHONE_COLS  = ["phone", "mobile", "cell", "whatsapp", "number",
                   "contact number", "phone number", "tel", "telephone"]

    def import_file(self, filepath: str, sheet_index: int = 0) -> ImportResult:
        """
        Auto-detect file type and import.
        Returns ImportResult with .contacts list of dicts.
        """
        path = Path(filepath)
        ext = path.suffix.lower()

        result = ImportResult()

        if ext == ".csv":
            result.source_type = "CSV"
            self._import_csv(filepath, result)
        elif ext in (".xls", ".xlsx", ".xlsm"):
            result.source_type = f"Excel ({ext})"
            self._import_excel(filepath, result, sheet_index)
        elif ext in (".html", ".htm"):
            result.source_type = "HTML"
            self._import_html(filepath, result)
        else:
            result.errors.append(f"Unsupported file type: {ext}")

        return result

    # ─── CSV ──────────────────────────────────────────────────────────────────

    def _import_csv(self, filepath: str, result: ImportResult):
        try:
            with open(filepath, newline="", encoding="utf-8-sig") as f:
                sample = f.read(4096)
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except Exception:
            dialect = csv.excel

        with open(filepath, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, dialect=dialect)
            col_map = self._map_columns(reader.fieldnames or [])
            result.columns_found = list(reader.fieldnames or [])
            for row in reader:
                contact = self._extract_contact(row, col_map)
                if contact:
                    result.contacts.append(contact)
                    result.total += 1
                else:
                    result.skipped += 1

    # ─── Excel ────────────────────────────────────────────────────────────────

    def _import_excel(self, filepath: str, result: ImportResult, sheet_index: int):
        try:
            import openpyxl
        except ImportError:
            result.errors.append("openpyxl not installed. Run: pip install openpyxl")
            return

        wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
        sheet = wb.worksheets[sheet_index]
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            result.errors.append("Excel sheet is empty.")
            return

        headers = [str(c).strip() if c is not None else "" for c in rows[0]]
        result.columns_found = headers
        col_map = self._map_columns(headers)

        for raw_row in rows[1:]:
            row = {headers[i]: (str(raw_row[i]).strip() if raw_row[i] is not None else "")
                   for i in range(len(headers))}
            contact = self._extract_contact(row, col_map)
            if contact:
                result.contacts.append(contact)
                result.total += 1
            else:
                result.skipped += 1

    # ─── HTML ─────────────────────────────────────────────────────────────────

    def _import_html(self, filepath: str, result: ImportResult):
        try:
            from html.parser import HTMLParser
        except ImportError:
            result.errors.append("html.parser not available.")
            return

        with open(filepath, encoding="utf-8-sig", errors="replace") as f:
            content = f.read()

        tables = self._parse_html_tables(content)
        if not tables:
            result.errors.append("No <table> elements found in HTML file.")
            return

        # Use the largest table
        table = max(tables, key=lambda t: len(t))
        if len(table) < 2:
            result.errors.append("HTML table has fewer than 2 rows.")
            return

        headers = [str(c).strip() for c in table[0]]
        result.columns_found = headers
        col_map = self._map_columns(headers)

        for raw_row in table[1:]:
            row = {headers[i]: str(raw_row[i]).strip()
                   for i in range(min(len(headers), len(raw_row)))}
            contact = self._extract_contact(row, col_map)
            if contact:
                result.contacts.append(contact)
                result.total += 1
            else:
                result.skipped += 1

    def _parse_html_tables(self, html: str) -> list:
        """Minimal HTML table parser — no external deps."""
        tables = []
        # Find all <table>...</table>
        for table_html in re.findall(r'<table[^>]*>(.*?)</table>',
                                      html, re.DOTALL | re.IGNORECASE):
            rows = []
            for row_html in re.findall(r'<tr[^>]*>(.*?)</tr>',
                                        table_html, re.DOTALL | re.IGNORECASE):
                cells = re.findall(r'<t[hd][^>]*>(.*?)</t[hd]>',
                                   row_html, re.DOTALL | re.IGNORECASE)
                clean = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
                if any(clean):
                    rows.append(clean)
            if rows:
                tables.append(rows)
        return tables

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _map_columns(self, headers: list) -> dict:
        """
        Returns {"name": actual_col, "email": actual_col, "phone": actual_col}
        by fuzzy-matching against known aliases.
        """
        mapping = {}
        lower_headers = {h.lower().strip(): h for h in headers}

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

    def _extract_contact(self, row: dict, col_map: dict) -> Optional[dict]:
        """
        Extract a contact dict. Returns None if no usable data.
        Also copies all extra columns as custom fields.
        """
        contact = {}

        name  = row.get(col_map.get("name", ""), "").strip()
        email = row.get(col_map.get("email", ""), "").strip()
        phone = row.get(col_map.get("phone", ""), "").strip()

        if not any([name, email, phone]):
            return None

        contact["name"]  = name
        contact["email"] = self._clean_email(email)
        contact["phone"] = self._clean_phone(phone)

        # Carry forward ALL extra columns as custom fields
        for k, v in row.items():
            if k and k not in col_map.values():
                contact[f"custom_{k}"] = str(v).strip()

        return contact

    def _clean_email(self, email: str) -> str:
        email = email.strip().lower()
        return email if re.match(r"[^@]+@[^@]+\.[^@]+", email) else ""

    def _clean_phone(self, phone: str) -> str:
        digits = re.sub(r"[^\d+]", "", phone)
        return digits if len(digits) >= 7 else ""


# ─── Quick test ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        importer = UniversalDataImporter()
        result = importer.import_file(sys.argv[1])
        print(result.summary())
        for c in result.contacts[:5]:
            print(c)

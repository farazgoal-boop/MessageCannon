"""Tests for UniversalDataImporter."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.modules.data_importer import UniversalDataImporter


class TestDataImporter(unittest.TestCase):
    """CSV, Excel, HTML, JSON import tests."""

    def setUp(self) -> None:
        self.importer = UniversalDataImporter()

    def test_csv_import(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as handle:
            handle.write("name,email,phone\nAlice,alice@test.com,+923001234567\n")
            path = handle.name
        result = self.importer.import_file(path)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.contacts[0]["name"], "Alice")
        Path(path).unlink(missing_ok=True)

    def test_json_import(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8") as handle:
            json.dump([{"name": "Bob", "email": "bob@test.com", "phone": "+923001234568"}], handle)
            path = handle.name
        result = self.importer.import_file(path)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.contacts[0]["email"], "bob@test.com")
        Path(path).unlink(missing_ok=True)

    def test_html_import(self) -> None:
        html = """
        <table>
          <tr><th>name</th><th>email</th><th>phone</th></tr>
          <tr><td>Carol</td><td>carol@test.com</td><td>+923001234569</td></tr>
        </table>
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False, encoding="utf-8") as handle:
            handle.write(html)
            path = handle.name
        result = self.importer.import_file(path)
        self.assertEqual(result.total, 1)
        self.assertEqual(result.contacts[0]["name"], "Carol")
        Path(path).unlink(missing_ok=True)

    def test_vcf_import(self) -> None:
        vcf = """BEGIN:VCARD
FN:Dave Test
EMAIL:dave@test.com
TEL:+923001234570
END:VCARD
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".vcf", delete=False, encoding="utf-8") as handle:
            handle.write(vcf)
            path = handle.name
        result = self.importer.import_file(path)
        self.assertEqual(result.total, 1)
        self.assertIn("dave@test.com", result.contacts[0]["email"])
        Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

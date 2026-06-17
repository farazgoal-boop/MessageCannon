"""Tests for writable AppData path helpers."""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils import paths


class TestPaths(unittest.TestCase):
    """Ensure runtime data paths are writable and not install-relative."""

    def test_session_dir_is_under_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_data = Path(tmp) / "MessageCannon Pro"
            with patch.object(paths, "get_app_data_dir", return_value=app_data):
                session_dir = paths.get_session_dir()
                self.assertEqual(session_dir, app_data / "whatsapp_session")
                self.assertTrue(session_dir.exists())

    def test_session_dir_is_writable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_data = Path(tmp) / "MessageCannon Pro"
            app_data.mkdir()
            with patch.object(paths, "get_app_data_dir", return_value=app_data):
                session_dir = paths.get_session_dir()
                probe = session_dir / "write_test.txt"
                probe.write_text("ok", encoding="utf-8")
                self.assertEqual(probe.read_text(encoding="utf-8"), "ok")

    def test_database_path_is_under_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_data = Path(tmp) / "MessageCannon Pro"
            with patch.object(paths, "get_app_data_dir", return_value=app_data):
                db_path = paths.get_database_path()
                self.assertEqual(db_path, app_data / "data" / "messagecannon.db")

    def test_license_path_is_under_app_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            app_data = Path(tmp) / "MessageCannon Pro"
            with patch.object(paths, "get_app_data_dir", return_value=app_data):
                license_path = paths.get_license_path()
                self.assertEqual(license_path, app_data / "license.lic")

    @unittest.skipUnless(sys.platform == "win32", "Windows-specific AppData layout")
    def test_app_data_dir_uses_appdata_on_windows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_appdata = Path(tmp) / "Roaming"
            fake_appdata.mkdir()
            with patch.dict(os.environ, {"APPDATA": str(fake_appdata)}, clear=False):
                paths._migration_done = True
                app_dir = paths.get_app_data_dir()
                self.assertEqual(app_dir, fake_appdata / "MessageCannon Pro")
                self.assertTrue(app_dir.exists())


if __name__ == "__main__":
    unittest.main()

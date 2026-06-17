"""Writable per-user paths for runtime data (works from source or frozen EXE)."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_DATA_NAME = "MessageCannon Pro"
LEGACY_HOME_DIR = Path.home() / ".messagecannon"
LICENSE_FILENAME = "license.lic"

_migration_done = False


def get_app_data_dir() -> Path:
    """
    Writable per-user directory for sessions, database, logs, and license data.
    Safe when installed under Program Files or run as a portable script.
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".local" / "share"

    app_dir = base / APP_DATA_NAME
    app_dir.mkdir(parents=True, exist_ok=True)
    _migrate_legacy_data(app_dir)
    return app_dir


def get_session_dir() -> Path:
    """Writable directory for the WhatsApp/Selenium browser session."""
    session_dir = get_app_data_dir() / "whatsapp_session"
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def get_data_dir() -> Path:
    """Writable directory for the SQLite database."""
    data_dir = get_app_data_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_database_path() -> Path:
    """Full path to the SQLite database file."""
    return get_data_dir() / "messagecannon.db"


def get_config_dir() -> Path:
    """Writable directory for JSON config files."""
    config_dir = get_app_data_dir() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_logs_dir() -> Path:
    """Writable directory for log files."""
    logs_dir = get_app_data_dir() / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def get_reports_dir() -> Path:
    """Writable directory for exported delivery reports."""
    reports_dir = get_app_data_dir() / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    return reports_dir


def get_license_path() -> Path:
    """Path to the license activation file."""
    return get_app_data_dir() / LICENSE_FILENAME


def _migrate_legacy_data(app_dir: Path) -> None:
    """Copy data from the old ~/.messagecannon layout on first run."""
    global _migration_done
    if _migration_done or not LEGACY_HOME_DIR.exists():
        _migration_done = True
        return

    try:
        legacy_data = LEGACY_HOME_DIR / "data" / "messagecannon.db"
        target_data = app_dir / "data"
        target_data.mkdir(parents=True, exist_ok=True)
        target_db = target_data / "messagecannon.db"
        if legacy_data.exists() and not target_db.exists():
            shutil.copy2(legacy_data, target_db)

        legacy_license = LEGACY_HOME_DIR / LICENSE_FILENAME
        target_license = app_dir / LICENSE_FILENAME
        if legacy_license.exists() and not target_license.exists():
            shutil.copy2(legacy_license, target_license)

        legacy_config = LEGACY_HOME_DIR / "config"
        target_config = app_dir / "config"
        if legacy_config.exists() and legacy_config.is_dir():
            target_config.mkdir(parents=True, exist_ok=True)
            for item in legacy_config.iterdir():
                target_item = target_config / item.name
                if item.is_file() and not target_item.exists():
                    shutil.copy2(item, target_item)
    except OSError:
        pass
    finally:
        _migration_done = True

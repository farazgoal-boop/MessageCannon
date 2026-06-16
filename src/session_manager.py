"""Persistent Selenium session management for WhatsApp Web."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait

from .database.db_manager import DatabaseManager
from .utils.constants import WHATSAPP_WEB_URL
from .utils.logger import Logger


@dataclass
class SessionState:
    """Current WhatsApp session metadata."""

    is_active: bool
    expires_at: Optional[datetime]
    requires_qr: bool
    status_text: str


class SessionManager:
    """Manage a persisted Chrome profile for WhatsApp Web automation."""

    SESSION_KEY = "whatsapp_session_state"
    SESSION_TTL_HOURS = 48

    def __init__(self, session_dir: Optional[Path] = None):
        self.db = DatabaseManager()
        self.session_dir = (session_dir or Path("./whatsapp_session")).resolve()
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _default_state(self) -> Dict[str, str]:
        return {
            "created_at": "",
            "expires_at": "",
            "last_verified_at": "",
            "logged_out_at": "",
        }

    def _read_state(self) -> Dict[str, str]:
        state = self.db.get_setting_json(self.SESSION_KEY, self._default_state())
        if not isinstance(state, dict):
            return self._default_state()
        merged = self._default_state()
        merged.update({k: str(v) for k, v in state.items() if k in merged})
        return merged

    def _write_state(self, state: Dict[str, str]) -> None:
        self.db.set_setting_json(self.SESSION_KEY, state)

    def _parse_dt(self, value: str) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def _session_profile_exists(self) -> bool:
        return any(self.session_dir.iterdir())

    def mark_session_verified(self) -> None:
        now = datetime.now()
        expires_at = now + timedelta(hours=self.SESSION_TTL_HOURS)
        state = self._read_state()
        if not state.get("created_at"):
            state["created_at"] = now.isoformat()
        state["last_verified_at"] = now.isoformat()
        state["expires_at"] = expires_at.isoformat()
        state["logged_out_at"] = ""
        self._write_state(state)
        Logger.info("WhatsApp session marked active until %s", expires_at.isoformat())

    def get_session_state(self) -> SessionState:
        state = self._read_state()
        expires_at = self._parse_dt(state.get("expires_at", ""))
        logged_out_at = self._parse_dt(state.get("logged_out_at", ""))
        profile_exists = self._session_profile_exists()

        if logged_out_at is not None:
            return SessionState(False, expires_at, True, "Session expired - please scan QR")

        if not profile_exists or expires_at is None:
            return SessionState(False, None, True, "Session expired - please scan QR")

        if datetime.now() >= expires_at:
            return SessionState(False, expires_at, True, "Session expired - please scan QR")

        return SessionState(True, expires_at, False, "Active session available")

    def build_driver(self, headless: bool = False) -> webdriver.Chrome:
        """Create a Chrome driver bound to the persisted user profile."""
        options = Options()
        options.add_argument(f"user-data-dir={self.session_dir}")
        options.add_argument("--profile-directory=Default")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        if headless:
            options.add_argument("--headless=new")

        driver = webdriver.Chrome(service=Service(), options=options)
        driver.maximize_window()
        driver.get(WHATSAPP_WEB_URL)
        return driver

    def ensure_active_session(
        self,
        driver: webdriver.Chrome,
        wait_timeout: int = 60,
        qr_timeout: int = 120,
    ) -> SessionState:
        """Wait for either an existing session or a fresh QR-authenticated session."""
        state = self.get_session_state()
        if state.is_active:
            try:
                WebDriverWait(driver, wait_timeout).until(
                    lambda d: self._is_logged_in(d) or self._has_qr_screen(d)
                )
                if self._is_logged_in(driver):
                    self.mark_session_verified()
                    return self.get_session_state()
            except Exception:
                Logger.warning("Timed out confirming persisted WhatsApp session")

        try:
            WebDriverWait(driver, qr_timeout).until(
                lambda d: self._is_logged_in(d) or self._has_qr_screen(d)
            )
            if self._is_logged_in(driver):
                self.mark_session_verified()
                return self.get_session_state()
            return SessionState(False, None, True, "Session expired - please scan QR")
        except Exception:
            return SessionState(False, None, True, "Session expired - please scan QR")

    def logout(self) -> None:
        """Invalidate the saved session without opening the browser."""
        self.reset_session(mark_logged_out=True)

    def reset_session(self, mark_logged_out: bool = False) -> None:
        """Clear the persisted browser profile and mark the session inactive."""
        if self.session_dir.exists():
            shutil.rmtree(self.session_dir, ignore_errors=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)

        state = self._default_state()
        if mark_logged_out:
            state["logged_out_at"] = datetime.now().isoformat()
        self._write_state(state)
        Logger.info("WhatsApp session reset completed")

    def _is_logged_in(self, driver: webdriver.Chrome) -> bool:
        selectors = [
            "div[contenteditable='true'][data-tab='3']",
            "div[contenteditable='true'][role='textbox']",
            "#pane-side",
        ]
        for selector in selectors:
            try:
                if driver.find_elements("css selector", selector):
                    return True
            except Exception:
                continue
        return False

    def _has_qr_screen(self, driver: webdriver.Chrome) -> bool:
        selectors = [
            "canvas[aria-label='Scan me!']",
            "div[data-testid='qrcode']",
            "canvas",
        ]
        for selector in selectors:
            try:
                if driver.find_elements("css selector", selector):
                    return True
            except Exception:
                continue
        return False
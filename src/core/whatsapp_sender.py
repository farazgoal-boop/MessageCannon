"""WhatsApp Web sender with session persistence and delivery tracking."""

from __future__ import annotations

import random
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional
from urllib.parse import quote

from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from ..delivery_tracker import DeliveryTracker
from ..models import Contact
from ..session_manager import SessionManager, SessionState
from .whatsapp_accounts import WhatsAppAccount
from ..utils.constants import (
    JITTER_RANGE,
    MAX_MESSAGES_PER_SESSION,
    MAX_MESSAGE_DELAY,
    MIN_MESSAGE_DELAY,
    WHATSAPP_WEB_URL,
)
from ..utils.logger import Logger


ProgressCallback = Callable[[int, int, str], None]
EventCallback = Callable[[str, Dict[str, Any]], None]


class WhatsAppSender:
    """Automate sending through WhatsApp Web using Selenium."""

    def __init__(self, account: Optional[WhatsAppAccount] = None):
        """`account`: optional multi-number groundwork (Item 7, final
        completion pass). Every real call site in this app today constructs
        `WhatsAppSender()` with no argument, which behaves identically to
        before this change -- a single, default SessionManager/session
        directory. Passing a `WhatsAppAccount` gives this sender its own
        isolated Chrome profile directory and its own namespaced session
        state, so multiple accounts' sessions never collide -- the storage
        half of multi-number support. Not yet wired into a live rotating
        send loop (see core/whatsapp_accounts.py's module docstring)."""
        self.account = account
        if account is not None:
            from .whatsapp_accounts import get_account_session_dir
            self.session_manager = SessionManager(
                session_dir=get_account_session_dir(account), account_label=account.label)
        else:
            self.session_manager = SessionManager()
        self.delivery_tracker = DeliveryTracker()
        self.is_sending = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.stop_event = threading.Event()
        self.driver = None
        self.driver_lock = threading.RLock()
        self.sent_count = 0
        self.failed_count = 0

    def initialize(self) -> SessionState:
        """Launch the browser if needed and ensure a WhatsApp session is available."""
        with self.driver_lock:
            if self.driver is None:
                self.driver = self.session_manager.build_driver()

            state = self.session_manager.ensure_active_session(self.driver)
            if state.is_active:
                self.delivery_tracker.start_monitoring(self.resolve_tracked_message_status, interval_seconds=5)
            return state

    def shutdown(self) -> None:
        """Stop background monitoring and close the browser."""
        self.delivery_tracker.stop_monitoring()
        with self.driver_lock:
            if self.driver is not None:
                try:
                    self.driver.quit()
                except Exception:
                    Logger.warning("Failed to close Selenium driver cleanly")
                self.driver = None

    def get_session_state(self) -> SessionState:
        """Return current persisted session state."""
        return self.session_manager.get_session_state()

    def reset_session(self) -> None:
        """Clear the saved browser profile and force a fresh QR login."""
        self.shutdown()
        self.session_manager.reset_session(mark_logged_out=True)

    def export_report(self, format: str = "csv") -> Path:
        """Export delivery tracking data."""
        return self.delivery_tracker.export_report(format=format)

    def get_delivery_stats(self) -> Dict[str, Any]:
        """Return delivery tracking aggregates."""
        return self.delivery_tracker.get_stats()

    def get_recent_activity(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent outbound tracked messages."""
        return self.delivery_tracker.get_recent_messages(limit=limit)

    def send_messages(
        self,
        contacts: List[Contact],
        messages: List[str],
        delay: int = 30,
        use_jitter: bool = True,
        max_messages: int = MAX_MESSAGES_PER_SESSION,
        progress_callback: Optional[ProgressCallback] = None,
        event_callback: Optional[EventCallback] = None,
    ) -> Dict[str, Any]:
        """Send a batch of messages and continuously update tracking records."""
        if len(contacts) != len(messages):
            Logger.error("Contacts and messages count mismatch")
            return {"sent": 0, "failed": len(contacts), "total": len(contacts)}

        if not (MIN_MESSAGE_DELAY <= delay <= MAX_MESSAGE_DELAY):
            delay = 30

        capped_total = min(len(contacts), max_messages, MAX_MESSAGES_PER_SESSION)
        state = self.initialize()
        if state.requires_qr and not state.is_active:
            if event_callback:
                event_callback("session", {"status": state.status_text})
            return {"sent": 0, "failed": capped_total, "total": capped_total, "status": state.status_text}

        self.is_sending = True
        self.sent_count = 0
        self.failed_count = 0
        self.stop_event.clear()

        start_time = time.time()
        for index, (contact, message) in enumerate(zip(contacts[:capped_total], messages[:capped_total]), start=1):
            if self.stop_event.is_set():
                break

            self.pause_event.wait()
            if progress_callback:
                progress_callback(index, capped_total, f"Sending to {contact.phone}")

            tracked_id = self.delivery_tracker.create_message(contact.phone, message, status="pending")
            success = self._send_single_message(contact, message, tracked_id, event_callback)

            if success:
                self.sent_count += 1
            else:
                self.failed_count += 1

            if index < capped_total:
                time.sleep(self._calculate_delay(delay, use_jitter))

        elapsed_time = time.time() - start_time
        self.is_sending = False
        stats = self.get_delivery_stats()
        return {
            "sent": self.sent_count,
            "failed": self.failed_count,
            "total": capped_total,
            "elapsed_time": elapsed_time,
            "delivery_rate": stats.get("delivery_rate", 0.0),
        }

    def pause_sending(self) -> None:
        self.pause_event.clear()
        Logger.info("Message sending paused")

    def resume_sending(self) -> None:
        self.pause_event.set()
        Logger.info("Message sending resumed")

    def stop_sending(self) -> None:
        self.stop_event.set()
        self.pause_event.set()
        Logger.info("Message sending stopped")

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_sending": self.is_sending,
            "is_paused": not self.pause_event.is_set(),
            "sent": self.sent_count,
            "failed": self.failed_count,
            "session": self.get_session_state().status_text,
        }

    def get_progress(self, total: int) -> float:
        if total == 0:
            return 0.0
        return min(((self.sent_count + self.failed_count) / total) * 100.0, 100.0)

    def resolve_tracked_message_status(self, tracked_message: Dict[str, Any]) -> Optional[str]:
        """Inspect WhatsApp Web DOM to determine the current delivery status."""
        if self.driver is None:
            return None

        phone = str(tracked_message.get("phone") or "")
        message_text = str(tracked_message.get("message_text") or "")
        if not phone or not message_text:
            return None

        with self.driver_lock:
            try:
                self._open_chat(phone)
                message_element = self._find_message_element(message_text)
                return self._extract_status_from_message(message_element)
            except Exception as exc:
                Logger.debug(f"Could not resolve delivery status for {phone}: {exc}")
                return None

    def _send_single_message(
        self,
        contact: Contact,
        message: str,
        tracked_id: Optional[int],
        event_callback: Optional[EventCallback],
    ) -> bool:
        with self.driver_lock:
            try:
                self._open_chat(contact.phone, message)
                composer = self._wait_for_composer()
                if composer.text.strip() == "":
                    composer.send_keys(message)

                send_button = self._wait_for_send_button()
                send_button.click()

                message_element = self._wait_for_message_echo(message)
                resolved_status = self._extract_status_from_message(message_element) or "sent"

                if tracked_id is not None:
                    self.delivery_tracker.update_status(tracked_id, "sent")
                    whatsapp_message_id = message_element.get_attribute("data-id") or message_element.get_attribute("data-message-id")
                    if whatsapp_message_id:
                        self.delivery_tracker.db.update_tracked_message(
                            tracked_id,
                            whatsapp_message_id=whatsapp_message_id,
                        )
                    self.delivery_tracker.update_status(tracked_id, resolved_status)

                if event_callback:
                    event_callback(
                        "message",
                        {
                            "phone": contact.phone,
                            "message": message,
                            "status": resolved_status,
                        },
                    )
                return True
            except Exception as exc:
                Logger.error(f"Failed sending to {contact.phone}: {exc}")
                if tracked_id is not None:
                    self.delivery_tracker.update_status(tracked_id, "failed", error_reason=str(exc))
                if event_callback:
                    event_callback(
                        "message",
                        {
                            "phone": contact.phone,
                            "message": message,
                            "status": "failed",
                            "error": str(exc),
                        },
                    )
                return False

    def _open_chat(self, phone: str, message: Optional[str] = None) -> None:
        if self.driver is None:
            raise RuntimeError("WhatsApp driver is not initialized")

        chat_url = f"{WHATSAPP_WEB_URL}send?phone={phone}"
        if message is not None:
            chat_url += f"&text={quote(message)}"
        self.driver.get(chat_url)
        WebDriverWait(self.driver, 45).until(lambda driver: self._wait_targets_present(driver))

    def _wait_targets_present(self, driver) -> bool:
        selectors = [
            "div[contenteditable='true'][data-tab='10']",
            "div[contenteditable='true'][role='textbox']",
            "button[aria-label='Send']",
            "span[data-icon='send']",
        ]
        for selector in selectors:
            try:
                if driver.find_elements(By.CSS_SELECTOR, selector):
                    return True
            except Exception:
                continue
        return False

    def _wait_for_composer(self) -> WebElement:
        if self.driver is None:
            raise RuntimeError("WhatsApp driver is not initialized")

        selector_candidates = [
            (By.CSS_SELECTOR, "div[contenteditable='true'][data-tab='10']"),
            (By.CSS_SELECTOR, "div[contenteditable='true'][role='textbox']"),
            (By.XPATH, "//footer//div[@contenteditable='true']"),
        ]
        last_error: Optional[Exception] = None
        for by, selector in selector_candidates:
            try:
                return WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((by, selector)))
            except Exception as exc:
                last_error = exc
        raise TimeoutException("Message composer not found") from last_error

    def _wait_for_send_button(self) -> WebElement:
        if self.driver is None:
            raise RuntimeError("WhatsApp driver is not initialized")

        button_candidates = [
            (By.CSS_SELECTOR, "button[aria-label='Send']"),
            (By.XPATH, "//button[@aria-label='Send']"),
            (By.XPATH, "//span[@data-icon='send']/ancestor::button[1]"),
        ]
        last_error: Optional[Exception] = None
        for by, selector in button_candidates:
            try:
                return WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((by, selector)))
            except Exception as exc:
                last_error = exc
        raise TimeoutException("Send button not found") from last_error

    def _wait_for_message_echo(self, message: str) -> WebElement:
        if self.driver is None:
            raise RuntimeError("WhatsApp driver is not initialized")

        WebDriverWait(self.driver, 20).until(lambda driver: len(self._find_outgoing_messages()) > 0)
        end_time = time.time() + 20
        while time.time() < end_time:
            try:
                return self._find_message_element(message)
            except Exception:
                time.sleep(0.5)
        raise TimeoutException("Sent message did not appear in chat")

    def _find_message_element(self, message: str) -> WebElement:
        outgoing_messages = self._find_outgoing_messages()
        normalized_message = self._normalize_message(message)
        for element in reversed(outgoing_messages):
            text = self._normalize_message(element.text)
            if normalized_message and normalized_message in text:
                return element
        if outgoing_messages:
            return outgoing_messages[-1]
        raise TimeoutException("No outgoing messages found")

    def _find_outgoing_messages(self) -> List[WebElement]:
        if self.driver is None:
            return []

        selectors = [
            "div.message-out",
            "div[data-testid='msg-container'][data-is-outgoing='true']",
            "div[data-testid='msg-container']",
        ]
        for selector in selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if elements:
                    return elements
            except Exception:
                continue
        return []

    def _extract_status_from_message(self, message_element: WebElement) -> Optional[str]:
        icon_map = {
            "msg-check": "sent",
            "msg-dblcheck": "delivered",
            "msg-dblcheck-ack": "read",
        }
        for icon_name, status in icon_map.items():
            try:
                if message_element.find_elements(By.CSS_SELECTOR, f"span[data-icon='{icon_name}']"):
                    return status
            except Exception:
                continue

        try:
            aria_chunks = (message_element.get_attribute("aria-label") or "").lower()
            if "read" in aria_chunks:
                return "read"
            if "delivered" in aria_chunks:
                return "delivered"
            if "sent" in aria_chunks:
                return "sent"
        except Exception:
            pass
        return None

    def _calculate_delay(self, base_delay: int, use_jitter: bool) -> float:
        if not use_jitter:
            return float(base_delay)
        return float(max(1, base_delay + random.randint(-JITTER_RANGE, JITTER_RANGE)))

    def _normalize_message(self, message: str) -> str:
        return " ".join((message or "").split())
    
    def get_progress(self, total: int) -> float:
        """
        Get progress percentage.
        
        Args:
            total: Total messages
            
        Returns:
            Progress percentage (0-100)
        """
        if total == 0:
            return 0.0
        
        progress = ((self.sent_count + self.failed_count) / total) * 100
        return min(progress, 100.0)

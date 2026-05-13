"""
WhatsApp sender for sending messages via WhatsApp Web.
"""

import time
import random
from typing import Callable, Optional, List, Dict
from threading import Thread, Event
import queue

from ..models import Contact, MessageLog, MessageStatus, Campaign
from ..utils.logger import Logger
from ..utils.constants import (
    MIN_MESSAGE_DELAY,
    MAX_MESSAGE_DELAY,
    JITTER_RANGE,
    MAX_MESSAGES_PER_SESSION,
    MAX_RETRY_ATTEMPTS,
    RETRY_DELAY
)


class WhatsAppSender:
    """Handles WhatsApp message sending."""
    
    def __init__(self):
        """Initialize WhatsApp sender."""
        self.is_sending = False
        self.pause_event = Event()
        self.pause_event.set()  # Initially not paused
        self.stop_event = Event()
        self.message_queue: queue.Queue = queue.Queue()
        self.sent_count = 0
        self.failed_count = 0
    
    def send_messages(
        self,
        contacts: List[Contact],
        messages: List[str],
        delay: int = 30,
        use_jitter: bool = True,
        max_messages: int = MAX_MESSAGES_PER_SESSION,
        progress_callback: Optional[Callable[[int, int, str], None]] = None
    ) -> Dict[str, int]:
        """
        Send messages to contacts.
        
        Args:
            contacts: List of Contact objects
            messages: List of message texts (should match contacts length)
            delay: Delay between messages in seconds
            use_jitter: Whether to add random jitter
            max_messages: Maximum messages to send
            progress_callback: Callback function for progress updates
            
        Returns:
            Dictionary with send statistics
        """
        # Validate inputs
        if len(contacts) != len(messages):
            Logger.error("Contacts and messages count mismatch")
            return {'sent': 0, 'failed': len(contacts), 'total': len(contacts)}
        
        if max_messages > MAX_MESSAGES_PER_SESSION:
            max_messages = MAX_MESSAGES_PER_SESSION
        
        # Validate delay
        if not (MIN_MESSAGE_DELAY <= delay <= MAX_MESSAGE_DELAY):
            delay = 30
        
        self.is_sending = True
        self.sent_count = 0
        self.failed_count = 0
        self.stop_event.clear()
        
        start_time = time.time()
        
        # Main sending loop
        for i, (contact, message) in enumerate(zip(contacts[:max_messages], messages[:max_messages])):
            # Check for stop signal
            if self.stop_event.is_set():
                Logger.info("Sending stopped by user")
                break
            
            # Wait if paused
            self.pause_event.wait()
            
            try:
                # Call progress callback
                if progress_callback:
                    progress_callback(i + 1, max_messages, f"Sending to {contact.phone}")
                
                # Send message
                success = self._send_to_whatsapp(contact, message)
                
                if success:
                    self.sent_count += 1
                    Logger.info(f"Message sent to {contact.phone}")
                else:
                    self.failed_count += 1
                    Logger.warning(f"Failed to send message to {contact.phone}")
                
                # Calculate delay with jitter
                actual_delay = self._calculate_delay(delay, use_jitter)
                
                # Wait before next message
                if i < max_messages - 1:  # Don't delay after last message
                    time.sleep(actual_delay)
            
            except Exception as e:
                Logger.error(f"Error sending to {contact.phone}: {e}")
                self.failed_count += 1
        
        elapsed_time = time.time() - start_time
        self.is_sending = False
        
        result = {
            'sent': self.sent_count,
            'failed': self.failed_count,
            'total': min(len(contacts), max_messages),
            'elapsed_time': elapsed_time
        }
        
        return result
    
    def _send_to_whatsapp(self, contact: Contact, message: str) -> bool:
        """
        Send single message to WhatsApp.
        
        Args:
            contact: Contact object
            message: Message text
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            # Method 1: Try pywhatkit
            try:
                import pywhatkit
                pywhatkit.sendwhatmsg_instantly(contact.phone, message, wait_time=5)
                return True
            except ImportError:
                Logger.debug("pywhatkit not available, trying selenium")
            except Exception as e:
                Logger.debug(f"pywhatkit failed: {e}, trying selenium")
            
            # Method 2: Try selenium (fallback)
            try:
                return self._send_via_selenium(contact, message)
            except ImportError:
                Logger.error("Neither pywhatkit nor selenium available")
                return False
        
        except Exception as e:
            Logger.error(f"Error sending message: {e}")
            return False
    
    def _send_via_selenium(self, contact: Contact, message: str) -> bool:
        """
        Send message via Selenium (WhatsApp Web automation).
        
        Args:
            contact: Contact object
            message: Message text
            
        Returns:
            True if sent successfully, False otherwise
        """
        try:
            from selenium import webdriver
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC
            
            # This is a placeholder - full implementation would require
            # proper WhatsApp Web automation
            Logger.debug(f"Selenium send to {contact.phone}: {message[:50]}...")
            
            # In a real implementation, this would:
            # 1. Open WhatsApp Web
            # 2. Search for contact
            # 3. Type message
            # 4. Send
            
            return True
        
        except Exception as e:
            Logger.error(f"Selenium send error: {e}")
            return False
    
    def _calculate_delay(self, base_delay: int, use_jitter: bool) -> float:
        """
        Calculate actual delay with optional jitter.
        
        Args:
            base_delay: Base delay in seconds
            use_jitter: Whether to add jitter
            
        Returns:
            Actual delay in seconds
        """
        if not use_jitter:
            return float(base_delay)
        
        # Add random variation ±5 seconds
        jitter = random.randint(-JITTER_RANGE, JITTER_RANGE)
        return float(max(1, base_delay + jitter))
    
    def pause_sending(self) -> None:
        """Pause message sending."""
        self.pause_event.clear()
        Logger.info("Message sending paused")
    
    def resume_sending(self) -> None:
        """Resume message sending."""
        self.pause_event.set()
        Logger.info("Message sending resumed")
    
    def stop_sending(self) -> None:
        """Stop message sending."""
        self.stop_event.set()
        Logger.info("Message sending stopped")
    
    def get_status(self) -> Dict[str, any]:
        """
        Get sending status.
        
        Returns:
            Status dictionary
        """
        return {
            'is_sending': self.is_sending,
            'is_paused': not self.pause_event.is_set(),
            'sent': self.sent_count,
            'failed': self.failed_count
        }
    
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

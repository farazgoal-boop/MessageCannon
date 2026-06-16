"""Bulk email sender using SMTP with custom pacing, variable substitution, and logging."""

import os
import smtplib
import threading
import time
import random
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional, Callable, Tuple
from pathlib import Path

from ..models import Contact, MessageLog, MessageStatus
from ..database.db_manager import DatabaseManager
from ..utils.logger import Logger

ProgressCallback = Callable[[int, int, str], None]
EventCallback = Callable[[str, Dict[str, Any]], None]


class EmailSender:
    """Automate sending bulk emails via SMTP."""

    def __init__(self):
        self.db = DatabaseManager()
        self.is_sending = False
        self.pause_event = threading.Event()
        self.pause_event.set()
        self.stop_event = threading.Event()
        self.sent_count = 0
        self.failed_count = 0

    def test_connection(self, config: Dict[str, Any]) -> Tuple[bool, str]:
        """Test SMTP connection and authentication."""
        host = config.get("host", "").strip()
        port = int(config.get("port", 587))
        user = config.get("username", "").strip()
        password = config.get("password", "").strip()
        use_ssl = config.get("use_ssl", False)

        if not host or not user or not password:
            return False, "Host, username, and password are required."

        server = None
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)
                server.ehlo()
                server.starttls()
                server.ehlo()
            
            server.login(user, password)
            server.quit()
            return True, "SMTP connection successful!"
        except Exception as exc:
            Logger.error(f"SMTP connection test failed: {exc}")
            return False, str(exc)
        finally:
            if server:
                try:
                    server.close()
                except Exception:
                    pass

    def send_emails(
        self,
        contacts: List[Contact],
        subject_template: str,
        body_template: str,
        smtp_config: Dict[str, Any],
        delay: int = 5,
        use_jitter: bool = True,
        progress_callback: Optional[ProgressCallback] = None,
        event_callback: Optional[EventCallback] = None,
    ) -> Dict[str, Any]:
        """Send a batch of emails in the background with template variables substituted."""
        if not contacts:
            return {"sent": 0, "failed": 0, "total": 0}

        self.is_sending = True
        self.sent_count = 0
        self.failed_count = 0
        self.stop_event.clear()
        self.pause_event.set()

        host = smtp_config.get("host", "").strip()
        port = int(smtp_config.get("port", 587))
        user = smtp_config.get("username", "").strip()
        password = smtp_config.get("password", "").strip()
        use_ssl = smtp_config.get("use_ssl", False)

        total_count = len(contacts)
        start_time = time.time()

        # Build campaign ID placeholder or save campaign details
        campaign_name = f"Email Campaign {time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Save SMTP settings to database (key: smtp_settings)
        self.db.set_setting_json("smtp_settings", {
            "host": host,
            "port": port,
            "username": user,
            "use_ssl": use_ssl
            # Do not store password or store it encrypted. For simplicity of a local client, we can store it as is or omit it.
        })

        for index, contact in enumerate(contacts, start=1):
            if self.stop_event.is_set():
                break

            self.pause_event.wait()

            if not contact.email:
                self.failed_count += 1
                if progress_callback:
                    progress_callback(index, total_count, f"Skipping {contact.name or 'Contact'} - No Email")
                continue

            if progress_callback:
                progress_callback(index, total_count, f"Sending email to {contact.email}")

            # Substitute variables
            subject = self._substitute_vars(subject_template, contact)
            body = self._substitute_vars(body_template, contact)

            # Create message log
            log_entry = MessageLog(
                campaign_id=None,
                contact_phone=contact.phone or "",
                contact_email=contact.email,
                contact_name=contact.name or "",
                subject=subject,
                message_text=body,
                status=MessageStatus.PENDING
            )
            log_id = self.db.add_message_log(log_entry)

            # Send single email
            success, error_msg = self._send_single_email(
                host, port, user, password, use_ssl, contact.email, subject, body
            )

            if success:
                self.sent_count += 1
                if log_id:
                    self.db.add_message_log(MessageLog(
                        id=log_id,
                        status=MessageStatus.SENT,
                        sent_at=datetime.now()
                    ))
                if event_callback:
                    event_callback("message", {"email": contact.email, "status": "sent"})
            else:
                self.failed_count += 1
                if log_id:
                    self.db.add_message_log(MessageLog(
                        id=log_id,
                        status=MessageStatus.FAILED,
                        error_message=error_msg
                    ))
                if event_callback:
                    event_callback("message", {"email": contact.email, "status": "failed", "error": error_msg})

            # Delay pacing
            if index < total_count and not self.stop_event.is_set():
                current_delay = delay
                if use_jitter:
                    current_delay += random.randint(-2, 2)
                time.sleep(max(1, current_delay))

        self.is_sending = False
        elapsed_time = time.time() - start_time
        return {
            "sent": self.sent_count,
            "failed": self.failed_count,
            "total": total_count,
            "elapsed_time": elapsed_time
        }

    def pause_sending(self) -> None:
        self.pause_event.clear()
        Logger.info("Email sending paused")

    def resume_sending(self) -> None:
        self.pause_event.set()
        Logger.info("Email sending resumed")

    def stop_sending(self) -> None:
        self.stop_event.set()
        self.pause_event.set()
        Logger.info("Email sending stopped")

    def _send_single_email(
        self,
        host: str,
        port: int,
        user: str,
        password: str,
        use_ssl: bool,
        recipient: str,
        subject: str,
        body: str
    ) -> Tuple[bool, str]:
        """Establish a connection and dispatch a single MIME email message."""
        server = None
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = user
            msg["To"] = recipient

            # Attach plain text
            msg.attach(MIMEText(body, "plain"))

            # Simple conversion to HTML for rich visualization in email clients
            html_body = body.replace("\n", "<br>")
            html_content = f"""
            <html>
                <body style="font-family: Arial, sans-serif; font-size: 14px; color: #333333; line-height: 1.5;">
                    {html_body}
                </body>
            </html>
            """
            msg.attach(MIMEText(html_content, "html"))

            # Connect
            if use_ssl:
                server = smtplib.SMTP_SSL(host, port, timeout=15)
            else:
                server = smtplib.SMTP(host, port, timeout=15)
                server.ehlo()
                server.starttls()
                server.ehlo()

            server.login(user, password)
            server.sendmail(user, recipient, msg.as_string())
            server.quit()
            return True, ""
        except Exception as exc:
            Logger.error(f"Failed to send email to {recipient}: {exc}")
            return False, str(exc)
        finally:
            if server:
                try:
                    server.close()
                except Exception:
                    pass

    def _substitute_vars(self, template: str, contact: Contact) -> str:
        """Replace template placeholders with contact fields."""
        result = template
        result = result.replace("{name}", contact.name or "")
        result = result.replace("{phone}", contact.phone or "")
        result = result.replace("{email}", contact.email or "")
        
        # Substitute custom fields
        for k, v in contact.custom_fields.items():
            result = result.replace(f"{{{k}}}", str(v))
        return result

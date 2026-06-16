"""
MessageCannon Pro - Bulk Email Sender
Features: SMTP (Gmail/Outlook/custom), HTML templates,
          variable substitution, open tracking, rate limiting.
"""

import smtplib
import ssl
import time
import uuid
import logging
import threading
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dataclasses import dataclass, field
from typing import Optional, Callable
from pathlib import Path
import json
import re

logger = logging.getLogger(__name__)


# ─── Presets for common providers ────────────────────────────────────────────

SMTP_PRESETS = {
    "Gmail": {
        "host": "smtp.gmail.com",
        "port": 587,
        "use_tls": True,
        "note": "Use an App Password, not your main password."
    },
    "Outlook / Hotmail": {
        "host": "smtp-mail.outlook.com",
        "port": 587,
        "use_tls": True,
        "note": "Enable SMTP AUTH in account settings."
    },
    "Yahoo": {
        "host": "smtp.mail.yahoo.com",
        "port": 587,
        "use_tls": True,
        "note": "Use an App Password from Yahoo Security."
    },
    "Custom SMTP": {
        "host": "",
        "port": 587,
        "use_tls": True,
        "note": "Enter your SMTP server details below."
    },
}


@dataclass
class SMTPConfig:
    host: str
    port: int
    username: str
    password: str
    sender_name: str
    sender_email: str
    use_tls: bool = True
    use_ssl: bool = False

    def validate(self) -> list:
        errors = []
        if not self.host:
            errors.append("SMTP host is required.")
        if not self.username:
            errors.append("Username is required.")
        if not self.password:
            errors.append("Password is required.")
        if not self.sender_email or "@" not in self.sender_email:
            errors.append("Valid sender email is required.")
        return errors


@dataclass
class EmailCampaign:
    name: str
    subject: str
    body_html: str
    body_text: str = ""       # auto-generated if empty
    reply_to: str = ""
    attachments: list = field(default_factory=list)   # list of file paths
    delay_seconds: float = 5.0
    max_per_session: int = 200
    track_opens: bool = False
    tracking_pixel_url: str = ""   # your tracking server URL

    def render(self, contact: dict) -> tuple[str, str, str]:
        """
        Substitute {name}, {email}, {company} etc. from contact dict.
        Returns (subject, html_body, text_body)
        """
        variables = {
            "name":    contact.get("name", ""),
            "email":   contact.get("email", ""),
            "phone":   contact.get("phone", ""),
        }
        # Add all custom_* fields
        for k, v in contact.items():
            if k.startswith("custom_"):
                variables[k[7:]] = v      # strip "custom_" prefix

        def substitute(text: str) -> str:
            for key, val in variables.items():
                text = text.replace(f"{{{key}}}", val)
            return text

        subject  = substitute(self.subject)
        body_html = substitute(self.body_html)
        body_text = substitute(self.body_text) if self.body_text \
                    else self._html_to_text(body_html)

        # Inject tracking pixel
        if self.track_opens and self.tracking_pixel_url:
            pixel_id = uuid.uuid4().hex
            pixel_url = f"{self.tracking_pixel_url}?id={pixel_id}&email={contact.get('email','')}"
            body_html += f'<img src="{pixel_url}" width="1" height="1" style="display:none"/>'

        return subject, body_html, body_text

    @staticmethod
    def _html_to_text(html: str) -> str:
        text = re.sub(r'<br\s*/?>', '\n', html, flags=re.IGNORECASE)
        text = re.sub(r'<p[^>]*>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        return text.strip()


@dataclass
class SendResult:
    total: int = 0
    sent: int = 0
    failed: int = 0
    skipped: int = 0
    errors: list = field(default_factory=list)
    stopped_early: bool = False


class BulkEmailSender:
    """
    Thread-safe bulk emailer.
    Runs on a background thread; reports progress via callbacks.
    """

    def __init__(self):
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    # ─── Connection test ─────────────────────────────────────────────────────

    def test_connection(self, config: SMTPConfig) -> tuple[bool, str]:
        """Try connecting and authenticating. Returns (ok, message)."""
        errors = config.validate()
        if errors:
            return False, "\n".join(errors)
        try:
            conn = self._connect(config)
            conn.quit()
            return True, "Connection successful ✅"
        except smtplib.SMTPAuthenticationError:
            return False, "Authentication failed. Check username/password (or App Password)."
        except smtplib.SMTPConnectError as e:
            return False, f"Cannot connect to {config.host}:{config.port} — {e}"
        except Exception as e:
            return False, f"Error: {e}"

    # ─── Send campaign ───────────────────────────────────────────────────────

    def send_campaign(
        self,
        config: SMTPConfig,
        campaign: EmailCampaign,
        contacts: list[dict],
        on_progress: Optional[Callable] = None,
        on_done:     Optional[Callable] = None,
    ):
        """
        Start sending in a background thread.
        on_progress(sent, failed, total, current_email)
        on_done(result: SendResult)
        """
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(config, campaign, contacts, on_progress, on_done),
            daemon=True,
        )
        self._thread.start()

    def stop(self):
        self._stop_event.set()

    # ─── Internal ────────────────────────────────────────────────────────────

    def _run(self, config, campaign, contacts, on_progress, on_done):
        result = SendResult(total=len(contacts))
        conn = None

        try:
            conn = self._connect(config)
        except Exception as e:
            result.errors.append(f"SMTP connection failed: {e}")
            if on_done:
                on_done(result)
            return

        for i, contact in enumerate(contacts):
            if self._stop_event.is_set():
                result.stopped_early = True
                break
            if result.sent >= campaign.max_per_session:
                result.stopped_early = True
                break

            email_addr = contact.get("email", "").strip()
            if not email_addr:
                result.skipped += 1
                continue

            try:
                subject, body_html, body_text = campaign.render(contact)
                msg = self._build_message(config, campaign, email_addr,
                                          subject, body_html, body_text)
                conn.sendmail(config.sender_email, email_addr, msg.as_string())
                result.sent += 1
                logger.info(f"Email sent → {email_addr}")
            except smtplib.SMTPServerDisconnected:
                # Reconnect once
                try:
                    conn = self._connect(config)
                    conn.sendmail(config.sender_email, email_addr, msg.as_string())
                    result.sent += 1
                except Exception as e2:
                    result.failed += 1
                    result.errors.append(f"{email_addr}: {e2}")
            except Exception as e:
                result.failed += 1
                result.errors.append(f"{email_addr}: {e}")

            if on_progress:
                on_progress(result.sent, result.failed, result.total, email_addr)

            # Rate limiting
            if i < len(contacts) - 1 and not self._stop_event.is_set():
                time.sleep(campaign.delay_seconds)

        try:
            conn.quit()
        except Exception:
            pass

        if on_done:
            on_done(result)

    def _connect(self, config: SMTPConfig):
        if config.use_ssl:
            context = ssl.create_default_context()
            conn = smtplib.SMTP_SSL(config.host, config.port, context=context)
        else:
            conn = smtplib.SMTP(config.host, config.port)
            if config.use_tls:
                conn.starttls(context=ssl.create_default_context())
        conn.login(config.username, config.password)
        return conn

    def _build_message(self, config, campaign, to_email,
                        subject, body_html, body_text):
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"{config.sender_name} <{config.sender_email}>"
        msg["To"]      = to_email
        if campaign.reply_to:
            msg["Reply-To"] = campaign.reply_to

        msg.attach(MIMEText(body_text, "plain", "utf-8"))
        msg.attach(MIMEText(body_html, "html",  "utf-8"))

        # Attachments
        for filepath in campaign.attachments:
            if not Path(filepath).exists():
                continue
            with open(filepath, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition",
                            f'attachment; filename="{Path(filepath).name}"')
            msg.attach(part)

        return msg


# ─── HTML Email Template Library ─────────────────────────────────────────────

EMAIL_TEMPLATES = {
    "Professional Announcement": {
        "subject": "Important Update from {company}",
        "html": """
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e0e0e0;border-radius:8px;overflow:hidden">
  <div style="background:#1a1a2e;padding:24px;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:24px">MessageCannon Pro</h1>
  </div>
  <div style="padding:32px">
    <p style="font-size:16px;color:#333">Dear <strong>{name}</strong>,</p>
    <p style="font-size:15px;color:#555;line-height:1.6">
      We have an important update to share with you.
    </p>
    <div style="margin:24px 0;padding:16px;background:#f5f5f5;border-left:4px solid #6c63ff;border-radius:4px">
      <p style="margin:0;color:#333">Your message here.</p>
    </div>
    <p style="color:#555">Best regards,<br><strong>{sender}</strong></p>
  </div>
  <div style="background:#f9f9f9;padding:16px;text-align:center;font-size:12px;color:#999">
    To unsubscribe, reply with STOP.
  </div>
</div>""",
    },
    "Promotional Offer": {
        "subject": "🎉 Special Offer Just for You, {name}!",
        "html": """
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:linear-gradient(135deg,#667eea,#764ba2);padding:40px;text-align:center">
    <h1 style="color:#fff;margin:0;font-size:28px">🎉 Special Offer</h1>
    <p style="color:rgba(255,255,255,0.9);font-size:18px">Just for you, {name}!</p>
  </div>
  <div style="padding:32px;background:#fff">
    <p style="font-size:16px;color:#333">Hi <strong>{name}</strong>,</p>
    <p style="color:#555;line-height:1.6">We have an exclusive offer waiting for you.</p>
    <div style="text-align:center;margin:32px 0">
      <a href="#" style="background:#764ba2;color:#fff;padding:14px 32px;border-radius:30px;text-decoration:none;font-size:16px;font-weight:bold">
        Claim Your Offer →
      </a>
    </div>
    <p style="color:#999;font-size:12px;text-align:center">
      To unsubscribe, reply STOP.
    </p>
  </div>
</div>""",
    },
    "Appointment Reminder": {
        "subject": "Reminder: Your Appointment on {date}",
        "html": """
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;border:1px solid #e0e0e0;border-radius:8px">
  <div style="background:#0f9b8e;padding:24px;text-align:center">
    <h2 style="color:#fff;margin:0">📅 Appointment Reminder</h2>
  </div>
  <div style="padding:32px">
    <p>Dear <strong>{name}</strong>,</p>
    <p>This is a friendly reminder about your upcoming appointment.</p>
    <table style="width:100%;border-collapse:collapse;margin:16px 0">
      <tr style="background:#f0fafa">
        <td style="padding:10px 16px;font-weight:bold;border-bottom:1px solid #e0e0e0">Date</td>
        <td style="padding:10px 16px;border-bottom:1px solid #e0e0e0">{date}</td>
      </tr>
      <tr>
        <td style="padding:10px 16px;font-weight:bold">Time</td>
        <td style="padding:10px 16px">{time}</td>
      </tr>
    </table>
    <p>Please contact us if you need to reschedule.</p>
    <p>Warm regards,<br><strong>{sender}</strong></p>
  </div>
</div>""",
    },
    "Invoice / Payment": {
        "subject": "Invoice #{invoice_no} — Amount Due: {amount}",
        "html": """
<div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto">
  <div style="background:#1e3a5f;padding:24px">
    <h2 style="color:#fff;margin:0">Invoice #{invoice_no}</h2>
  </div>
  <div style="padding:32px">
    <p>Dear <strong>{name}</strong>,</p>
    <p>Please find your invoice details below:</p>
    <div style="border:1px solid #e0e0e0;border-radius:8px;padding:16px;margin:16px 0">
      <p><strong>Amount Due:</strong> {amount}</p>
      <p><strong>Due Date:</strong> {date}</p>
    </div>
    <p>Thank you for your business.</p>
    <p>Best regards,<br><strong>{sender}</strong></p>
  </div>
</div>""",
    },
}


def get_template_names():
    return list(EMAIL_TEMPLATES.keys())


def get_template(name: str) -> dict:
    return EMAIL_TEMPLATES.get(name, {})

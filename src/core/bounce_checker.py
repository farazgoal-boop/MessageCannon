"""Real bounce/NDR (non-delivery report) detection against the sending
account's own inbox, via IMAP.

The existing email send path (`main_window.py:_send_email_campaign`) marks a
message `status=SENT` the instant the SMTP server *accepts* it for delivery
-- that is not the same thing as the message actually reaching the
recipient. A hard bounce (mailbox doesn't exist, domain blocks delivery,
etc.) comes back afterward as a *separate* bounce/NDR message delivered to
the sending account's own inbox, on its own schedule (seconds to several
minutes later, sometimes longer) -- nothing in the send path itself can ever
see that. This module closes that gap: it reads the inbox (read-only, never
modifies/deletes/flags anything) looking for real NDR messages, and
cross-references the addresses they report as failed against the specific
set of addresses a given campaign actually sent to.

Never raises: any connection/auth/parse failure is reported via
`BounceCheckResult.ok=False` / `.error`, the same defensive contract this
app already uses for `update_checker.check_for_update` -- a bounce check
failing (offline, wrong IMAP settings, provider quirk) must never crash a
background thread or block the app; it just means "couldn't check right
now," and the campaign's own Sent/Failed counts from send-time are
untouched either way.
"""

from __future__ import annotations

import email
import imaplib
import re
import socket
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from email.message import Message
from typing import Dict, Optional, Set, Tuple


# Real IMAP host/port for the same providers Settings' own SMTP "Provider"
# preset dropdown already offers (main_window.py's SMTP_PRESETS) -- app
# passwords / equivalent credentials work identically for SMTP and IMAP on
# every one of these, so no separate IMAP credential is ever needed.
IMAP_PRESETS: Dict[str, Tuple[str, int]] = {
    "Gmail":   ("imap.gmail.com", 993),
    "Outlook": ("outlook.office365.com", 993),
    "Yahoo":   ("imap.mail.yahoo.com", 993),
}

_SMTP_HOST_TO_IMAP: Dict[str, Tuple[str, int]] = {
    "smtp.gmail.com": IMAP_PRESETS["Gmail"],
    "smtp-mail.outlook.com": IMAP_PRESETS["Outlook"],
    "smtp.office365.com": IMAP_PRESETS["Outlook"],
    "smtp.mail.yahoo.com": IMAP_PRESETS["Yahoo"],
}

BOUNCE_SENDER_PATTERNS = (
    "mailer-daemon", "mailer daemon", "postmaster",
    "mail delivery subsystem", "mail delivery system",
)
BOUNCE_SUBJECT_PATTERNS = (
    "undeliverable", "undelivered mail", "delivery status notification",
    "delivery has failed", "delivery failed", "returned mail",
    "failure notice", "address not found", "message blocked",
    "mail delivery failed", "delivery incomplete", "wasn't delivered",
)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")


def guess_imap_host(smtp_host: str, provider: str = "") -> Optional[Tuple[str, int]]:
    """Best-effort IMAP (host, port) for the mailbox a given SMTP host
    sends through. Prefers an exact provider-name match (from the same
    "Provider" preset the SMTP settings already use), then an exact known
    SMTP-host match, then a generic "smtp." -> "imap." prefix swap for an
    unrecognized custom host. Returns None when nothing sensible can be
    guessed -- callers must treat that as "can't check bounces for this
    provider" (a real, disclosed limitation), never as an error to raise."""
    if provider in IMAP_PRESETS:
        return IMAP_PRESETS[provider]
    host = (smtp_host or "").strip().lower()
    if host in _SMTP_HOST_TO_IMAP:
        return _SMTP_HOST_TO_IMAP[host]
    if host.startswith("smtp."):
        return (host.replace("smtp.", "imap.", 1), 993)
    return None


@dataclass
class ParsedBounce:
    is_bounce: bool
    failed_recipients: Set[str] = field(default_factory=set)
    reason: str = ""


def _looks_like_bounce_sender(from_header: str) -> bool:
    low = (from_header or "").lower()
    return any(p in low for p in BOUNCE_SENDER_PATTERNS)


def _looks_like_bounce_subject(subject: str) -> bool:
    low = (subject or "").lower()
    return any(p in low for p in BOUNCE_SUBJECT_PATTERNS)


def _decode_part_text(part: Message) -> str:
    try:
        payload = part.get_payload(decode=True)
        if not payload:
            return ""
        return payload.decode(part.get_content_charset() or "utf-8", errors="replace")
    except Exception:
        return ""


def _dsn_field_blocks(part: Message):
    """A real `message/delivery-status` part is parsed by Python's own
    `email` package as a *list of sub-Message objects* (one per
    per-recipient field block, per RFC 3464) -- Final-Recipient/
    Diagnostic-Code/etc. are real headers on each sub-message, not flat
    body text. Confirmed directly (not assumed) by inspecting a real
    constructed DSN part: `part.is_multipart()` is True and
    `part.get_payload()` returns `[Message, Message, ...]`, so
    `get_payload(decode=True)` (correct for a genuine text part) silently
    returns nothing here. Falls back to scanning the part as flat text for
    any provider that sends a non-standard, unparsed delivery-status part
    instead."""
    payload = part.get_payload()
    if isinstance(payload, list) and payload:
        for block in payload:
            if hasattr(block, "items"):
                yield block
    else:
        # Fallback: treat the whole part as one flat "block" of
        # "Field: value" lines, mimicking a Message's .get() interface.
        text = _decode_part_text(part)
        fields: Dict[str, str] = {}
        for line in text.splitlines():
            if ":" in line:
                key, _, value = line.partition(":")
                fields.setdefault(key.strip(), value.strip())
        if fields:
            class _FieldBlock:
                def get(self_, key, default=None):
                    return fields.get(key, default)
            yield _FieldBlock()


def _extract_recipients_from_dsn_part(part: Message) -> Set[str]:
    """RFC 3464 machine-readable message/delivery-status part --
    Final-Recipient / Original-Recipient headers, the authoritative source
    when a provider includes one (Gmail, Outlook, and most real mail
    servers do)."""
    recipients: Set[str] = set()
    for block in _dsn_field_blocks(part):
        for header_name in ("Final-Recipient", "Original-Recipient"):
            value = block.get(header_name)
            if value:
                match = EMAIL_RE.search(value)
                if match:
                    recipients.add(match.group(0).lower())
    return recipients


def _extract_reason_from_dsn_part(part: Message) -> str:
    for block in _dsn_field_blocks(part):
        for header_name in ("Diagnostic-Code", "Status"):
            value = block.get(header_name)
            if value and value.strip():
                return value.strip()
    return ""


def _scan_body_for_addresses(msg: Message) -> Set[str]:
    """Fallback for providers that send a plain-text bounce with no
    structured DSN part -- scans the human-readable body for any email
    address. Only ever called once a message is already confirmed a bounce
    by sender/subject/DSN-part; a body full of addresses proves nothing on
    its own and is never used to *decide* is_bounce."""
    found: Set[str] = set()
    try:
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_type() in ("text/plain", "text/html"):
                    found |= {m.lower() for m in EMAIL_RE.findall(_decode_part_text(part))}
        else:
            found |= {m.lower() for m in EMAIL_RE.findall(_decode_part_text(msg))}
    except Exception:
        pass
    return found


def parse_bounce_message(msg: Message) -> ParsedBounce:
    """Pure -- given a real `email.message.Message` (one already-fetched
    inbox message), determines whether it's a bounce/NDR and, if so, which
    real recipient address(es) it reports as failed and why.

    Prefers the structured RFC 3464 `message/delivery-status` part when
    present (the reliable case most real providers use); falls back to a
    sender/subject heuristic plus a body address-scan when no structured
    part exists."""
    from_header = msg.get("From", "")
    subject = msg.get("Subject", "")
    sender_says_bounce = _looks_like_bounce_sender(from_header)
    subject_says_bounce = _looks_like_bounce_subject(subject)

    recipients: Set[str] = set()
    reason = ""
    has_dsn_part = False

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "message/delivery-status":
                has_dsn_part = True
                recipients |= _extract_recipients_from_dsn_part(part)
                if not reason:
                    reason = _extract_reason_from_dsn_part(part)

    is_bounce = has_dsn_part or sender_says_bounce or subject_says_bounce
    if not is_bounce:
        return ParsedBounce(is_bounce=False)

    if not recipients:
        recipients = _scan_body_for_addresses(msg)

    if not reason:
        reason = subject.strip() or "Delivery failed (no further detail in the bounce message)"

    return ParsedBounce(is_bounce=True, failed_recipients=recipients, reason=reason)


@dataclass
class BounceCheckResult:
    ok: bool
    error: str = ""
    bounces: Dict[str, str] = field(default_factory=dict)  # lowercased email -> reason
    messages_scanned: int = 0


def check_for_bounces(host: str, port: int, username: str, password: str,
                       candidate_emails: Set[str], since_days: int = 14) -> BounceCheckResult:
    """Real, read-only IMAP scan of the sending account's own inbox for
    bounce/NDR messages whose failed-recipient address is one we actually
    sent to (`candidate_emails`) -- irrelevant NDRs for other mail are
    ignored. Opens INBOX with `readonly=True` and never marks a message
    read/moves/deletes it. Never raises: any connection/login/search
    failure is reported via `result.ok=False`/`result.error`.
    """
    candidates_lower = {e.strip().lower() for e in candidate_emails if e}
    if not candidates_lower:
        return BounceCheckResult(ok=True, bounces={})

    try:
        conn = imaplib.IMAP4_SSL(host, port, timeout=20)
    except (OSError, socket.error, imaplib.IMAP4.error) as exc:
        return BounceCheckResult(ok=False, error=f"Could not connect to {host}:{port} — {exc}")

    try:
        try:
            conn.login(username, password)
        except imaplib.IMAP4.error as exc:
            return BounceCheckResult(ok=False, error=f"IMAP login failed: {exc}")

        try:
            status, _data = conn.select("INBOX", readonly=True)
            if status != "OK":
                return BounceCheckResult(ok=False, error="Could not open INBOX (read-only)")
        except imaplib.IMAP4.error as exc:
            return BounceCheckResult(ok=False, error=f"Could not open INBOX: {exc}")

        since_str = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime("%d-%b-%Y")
        candidate_ids: Set[bytes] = set()
        try:
            for criteria in (
                f'(SINCE {since_str} FROM "mailer-daemon")',
                f'(SINCE {since_str} FROM "postmaster")',
                f'(SINCE {since_str} SUBJECT "Undeliverable")',
                f'(SINCE {since_str} SUBJECT "Delivery Status Notification")',
            ):
                status, data = conn.search(None, criteria)
                if status == "OK" and data and data[0]:
                    candidate_ids |= set(data[0].split())
        except imaplib.IMAP4.error as exc:
            return BounceCheckResult(ok=False, error=f"IMAP search failed: {exc}")

        bounces: Dict[str, str] = {}
        scanned = 0
        for msg_id in candidate_ids:
            try:
                status, msg_data = conn.fetch(msg_id, "(RFC822)")
                if status != "OK" or not msg_data or not msg_data[0]:
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)
            except Exception:
                continue
            scanned += 1
            parsed = parse_bounce_message(msg)
            if not parsed.is_bounce:
                continue
            for addr in parsed.failed_recipients:
                if addr in candidates_lower and addr not in bounces:
                    bounces[addr] = parsed.reason

        return BounceCheckResult(ok=True, bounces=bounces, messages_scanned=scanned)
    finally:
        try:
            conn.logout()
        except Exception:
            pass

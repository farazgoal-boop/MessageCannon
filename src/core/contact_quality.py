"""
Item 34 (sub-item 4) of the multi-product generalization pass: a
contact-list quality check before a bulk send.

Rule-based, not AI -- role-based address detection is a well-known, fixed
pattern (info@, noreply@, ...), so a deterministic check is more reliable
and instant compared to an AI call for something this mechanical. Flags,
never blocks -- the user stays in control of who gets included, this just
makes an otherwise-invisible risk visible before they click send.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

# Common role-based/functional mailbox prefixes -- typically monitored by a
# team or an automated system rather than a real individual, so they tend to
# have poor engagement (opens/replies) for outreach/marketing sends, even
# though they're technically valid, deliverable addresses.
ROLE_BASED_PREFIXES = frozenset({
    "info", "noreply", "no-reply", "donotreply", "do-not-reply", "admin",
    "administrator", "support", "sales", "contact", "hello", "hi", "help",
    "webmaster", "postmaster", "abuse", "office", "team", "billing",
    "accounts", "careers", "jobs", "hr", "marketing", "newsletter",
    "subscribe", "unsubscribe", "mail", "email", "enquiries", "inquiries",
})


@dataclass(frozen=True)
class ContactQualityFlag:
    email: str
    reason: str


def is_role_based_address(email: str) -> bool:
    """True if `email`'s local part (before the @) matches a known
    role-based/functional prefix, e.g. "info@example.com"."""
    if not email or "@" not in email:
        return False
    local_part = email.split("@", 1)[0].strip().lower()
    return local_part in ROLE_BASED_PREFIXES


def flag_low_quality_emails(emails: Iterable[str]) -> List[ContactQualityFlag]:
    """Scans a list of real email addresses about to receive a bulk send
    and flags the ones that look role-based -- returns one flag per
    matching address, in input order, de-duplicated. This is purely
    informational: callers decide whether/how to surface it (e.g. a note
    in the pre-send confirmation dialog), never an automatic exclusion."""
    seen = set()
    flags: List[ContactQualityFlag] = []
    for email in emails:
        normalized = (email or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        if is_role_based_address(normalized):
            flags.append(ContactQualityFlag(
                email=email,
                reason="Role-based address (shared inbox, not a real individual) — "
                       "these typically have lower open/reply rates.",
            ))
    return flags

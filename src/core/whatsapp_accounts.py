"""Multi-number WhatsApp account groundwork (Item 7, final completion pass).

The high-volume sending strategy this app already has a documented roadmap
for hedged this exact item as "if feasible" — and it isn't fully feasible
to *finish* here: `WhatsAppSender`'s single-session model can be extended
to support multiple independent Chrome profiles (each with its own
persisted login), which is real, buildable, testable architecture — but a
live send loop that actually rotates between them mid-campaign needs a
real second WhatsApp-registered phone to verify against, which this
environment doesn't have. Per the user's own explicit instruction for this
item, this builds the real structural groundwork (account model, isolated
per-account session storage, a tested rotation-assignment algorithm, a
Settings UI to manage accounts) without touching `WhatsAppSender.send_messages`'s
actual, already-working, already-tested single-account send loop at all —
wiring live rotation into a real send is flagged as the explicit next step,
not silently skipped and not faked as done.

Storage: a plain JSON list under one settings key (`whatsapp_accounts`),
the same pattern already used for every other structured setting in this
app (`smtp_settings`, setup-wizard progress, etc.) — no new database table,
so this carries zero schema-migration risk against the live production
database.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import List, Optional

from ..utils.paths import get_session_dir

SETTINGS_KEY = "whatsapp_accounts"


@dataclass
class WhatsAppAccount:
    label: str
    session_dir_name: str  # subdirectory name under the shared session root

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "WhatsAppAccount":
        return cls(label=str(data["label"]), session_dir_name=str(data["session_dir_name"]))


def _slugify(label: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", label.strip()).strip("_").lower()
    return slug or "account"


def list_accounts(db) -> List[WhatsAppAccount]:
    raw = db.get_setting_json(SETTINGS_KEY, [])
    if not isinstance(raw, list):
        return []
    accounts = []
    for item in raw:
        if isinstance(item, dict) and "label" in item and "session_dir_name" in item:
            accounts.append(WhatsAppAccount.from_dict(item))
    return accounts


def save_accounts(db, accounts: List[WhatsAppAccount]) -> None:
    db.set_setting_json(SETTINGS_KEY, [a.to_dict() for a in accounts])


def add_account(db, label: str) -> WhatsAppAccount:
    """Raises ValueError on an empty or duplicate (case-insensitive) label
    -- the caller (Settings UI) surfaces that message directly rather than
    silently ignoring the request."""
    label = label.strip()
    if not label:
        raise ValueError("Account name cannot be empty.")

    accounts = list_accounts(db)
    if any(a.label.lower() == label.lower() for a in accounts):
        raise ValueError(f'An account named "{label}" already exists.')

    base_slug = _slugify(label)
    existing_dirs = {a.session_dir_name for a in accounts}
    slug = base_slug
    suffix = 2
    while slug in existing_dirs:
        slug = f"{base_slug}_{suffix}"
        suffix += 1

    account = WhatsAppAccount(label=label, session_dir_name=slug)
    accounts.append(account)
    save_accounts(db, accounts)
    return account


def remove_account(db, label: str) -> bool:
    accounts = list_accounts(db)
    filtered = [a for a in accounts if a.label != label]
    if len(filtered) == len(accounts):
        return False
    save_accounts(db, filtered)
    return True


def get_account_session_dir(account: WhatsAppAccount) -> Path:
    """A distinct, isolated Chrome profile directory per account, nested
    under the app's existing single session root (`get_session_dir()`) so
    every account's persisted login lives under the same real, already-
    correct per-user app-data location -- nothing about where session data
    lives on disk changes for the existing default (no-account) path."""
    account_dir = get_session_dir() / "accounts" / account.session_dir_name
    account_dir.mkdir(parents=True, exist_ok=True)
    return account_dir


def assign_account_for_message(
    accounts: List[WhatsAppAccount], message_index: int, messages_per_account: int,
) -> Optional[WhatsAppAccount]:
    """Pure round-robin rotation: which configured account should handle
    the message at `message_index` (0-based) in a batch, moving to the next
    account every `messages_per_account` messages and wrapping back to the
    first once every account has had a turn. Returns None when no accounts
    are configured, so a caller can fall back to the single default
    session -- exactly today's real, working, single-account behavior.

    Not yet wired into a real send loop (see module docstring) -- this is
    the tested rotation *algorithm*, verified in isolation, not yet driving
    live sends."""
    if not accounts:
        return None
    if messages_per_account <= 0:
        messages_per_account = 1
    account_index = (message_index // messages_per_account) % len(accounts)
    return accounts[account_index]

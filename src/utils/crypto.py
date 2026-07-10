"""Local encryption for user-supplied secrets (e.g. BYO AI API keys).

Never sends keys anywhere — encrypts at rest only, using a per-install
Fernet key stored alongside the app's other AppData files.
"""

from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken

from .paths import get_app_data_dir

_KEY_FILENAME = ".secret.key"


def _get_or_create_key() -> bytes:
    key_path = get_app_data_dir() / _KEY_FILENAME
    if key_path.exists():
        return key_path.read_bytes()

    key = Fernet.generate_key()
    key_path.write_bytes(key)
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return key


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a secret for local storage. Empty input returns empty output."""
    if not plaintext:
        return ""
    fernet = Fernet(_get_or_create_key())
    return fernet.encrypt(plaintext.encode("utf-8")).decode("utf-8")


def decrypt_secret(token: str) -> str:
    """Decrypt a secret previously produced by encrypt_secret. Returns "" on
    empty/missing/corrupt input rather than raising, since a stale or
    tampered key file must not crash settings load."""
    if not token:
        return ""
    try:
        fernet = Fernet(_get_or_create_key())
        return fernet.decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""

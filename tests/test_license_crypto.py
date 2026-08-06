"""Item 36 of the multi-product generalization pass: real, offline,
machine-bound license verification via Ed25519 signatures -- replacing the
previous single hardcoded PAID_PASSKEY (identical for every buyer, baked
into the shipped EXE). Mirrors JobMind Match's own proven scheme.

Uses a throwaway, test-only Ed25519 keypair (never the real seller signing
key at ~/.messagecannon-license-signing/private_key.pem) so this suite
never depends on sensitive, machine-specific material persisting outside
the repo -- the same verification code path is exercised regardless of
whose key signed the message.
"""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from src.utils import license_crypto as lc


@pytest.fixture()
def throwaway_keypair(monkeypatch):
    """Generates a real, fresh Ed25519 keypair for this test only, and
    points license_crypto's public-key verification at it -- so a real
    signature really does verify, and a wrong one really doesn't, without
    ever touching the real production signing key."""
    private_key = Ed25519PrivateKey.generate()
    public_bytes = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    monkeypatch.setattr(lc, "PUBLIC_KEY_B64", base64.b64encode(public_bytes).decode("ascii"))
    return private_key


def _sign(private_key: Ed25519PrivateKey, request_code: str) -> str:
    signature = private_key.sign(lc._normalize_code(request_code).encode("utf-8"))
    return lc.format_activation_code(signature)


def test_machine_request_code_has_the_real_prefix_and_is_stable():
    code1 = lc.machine_request_code()
    code2 = lc.machine_request_code()
    assert code1.startswith("MCP-")
    assert code1 == code2, "the same machine must always produce the same request code"


def test_machine_fingerprint_is_a_real_stable_hex_digest():
    fp1 = lc.machine_fingerprint()
    fp2 = lc.machine_fingerprint()
    assert fp1 == fp2
    assert len(fp1) == 24
    assert all(c in "0123456789ABCDEF" for c in fp1)


def test_real_signature_over_the_real_request_code_verifies(throwaway_keypair):
    """The literal end-to-end proof: a real request code, signed by a real
    (throwaway) private key, verifies as a real activation code."""
    request_code = lc.machine_request_code()
    activation_code = _sign(throwaway_keypair, request_code)
    assert activation_code.startswith("ACT-")
    assert lc.verify_activation_code(request_code, activation_code) is True


def test_signature_for_a_different_request_code_does_not_verify(throwaway_keypair):
    """The core machine-binding guarantee: a signature produced for one
    request code must not verify against a different one (simulating an
    activation code copied to a different machine, which would have a
    different real request code)."""
    real_code = lc.machine_request_code()
    activation_code = _sign(throwaway_keypair, real_code)
    assert lc.verify_activation_code("MCP-00000-00000-00000-00000", activation_code) is False


def test_garbage_activation_code_never_verifies(throwaway_keypair):
    request_code = lc.machine_request_code()
    assert lc.verify_activation_code(request_code, "not-a-real-code") is False
    assert lc.verify_activation_code(request_code, "") is False
    assert lc.verify_activation_code(request_code, "ACT-") is False


def test_activation_code_signed_by_a_different_key_does_not_verify():
    """A signature from a DIFFERENT private key than the one whose public
    key is embedded must never verify -- the actual security property this
    whole scheme rests on."""
    real_key = Ed25519PrivateKey.generate()
    impostor_key = Ed25519PrivateKey.generate()
    public_bytes = real_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    import src.utils.license_crypto as lc_module
    original = lc_module.PUBLIC_KEY_B64
    try:
        lc_module.PUBLIC_KEY_B64 = base64.b64encode(public_bytes).decode("ascii")
        request_code = lc_module.machine_request_code()
        forged = _sign(impostor_key, request_code)
        assert lc_module.verify_activation_code(request_code, forged) is False
    finally:
        lc_module.PUBLIC_KEY_B64 = original


def test_verify_never_raises_on_malformed_input(throwaway_keypair):
    request_code = lc.machine_request_code()
    for bad in ["ACT-@@@@@", None, 12345, "ACT-" + "Z" * 200, "ACT"]:
        try:
            result = lc.verify_activation_code(request_code, bad)  # type: ignore[arg-type]
        except Exception as exc:  # pragma: no cover - the assertion below is the real check
            pytest.fail(f"verify_activation_code raised on malformed input {bad!r}: {exc}")
        assert result is False


def test_format_activation_code_requires_a_real_ed25519_length_signature():
    with pytest.raises(ValueError):
        lc.format_activation_code(b"too-short")

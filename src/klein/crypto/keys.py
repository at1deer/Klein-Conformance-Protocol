"""Ed25519 key loading and encoding helpers for Klein test identities."""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from klein.common.hashing import sha256_bytes

CRYPTO_EXTRA_MESSAGE = (
    "Ed25519 support requires the 'cryptography' package. "
    "Install it with: pip install 'klein-protocol[crypto]'"
)


def _crypto_modules() -> tuple[Any, Any]:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:  # pragma: no cover - exercised when optional extra is absent.
        raise RuntimeError(CRYPTO_EXTRA_MESSAGE) from exc
    return serialization, ed25519


def load_ed25519_private_key(path: str | Path) -> Any:
    """Load a PEM-encoded Ed25519 private key."""
    serialization, ed25519 = _crypto_modules()
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    if not isinstance(key, ed25519.Ed25519PrivateKey):
        raise ValueError("private key is not an Ed25519 private key")
    return key


def load_ed25519_public_key(path: str | Path) -> Any:
    """Load a PEM-encoded Ed25519 public key."""
    serialization, ed25519 = _crypto_modules()
    key = serialization.load_pem_public_key(Path(path).read_bytes())
    if not isinstance(key, ed25519.Ed25519PublicKey):
        raise ValueError("public key is not an Ed25519 public key")
    return key


def raw_public_key(public_key: Any) -> bytes:
    """Return the raw 32-byte Ed25519 public key encoding."""
    serialization, _ = _crypto_modules()
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def public_key_from_raw(raw_key: bytes) -> Any:
    """Load an Ed25519 public key from its raw 32-byte encoding."""
    _, ed25519 = _crypto_modules()
    if len(raw_key) != 32:
        raise ValueError("raw Ed25519 public keys must be 32 bytes")
    return ed25519.Ed25519PublicKey.from_public_bytes(raw_key)


def encode_base64_raw(payload: bytes) -> str:
    """Return unwrapped base64 for raw Ed25519 key/signature bytes."""
    return base64.b64encode(payload).decode("ascii")


def decode_base64_raw(value: str, *, expected_length: int, label: str) -> bytes:
    """Decode strict base64 and enforce the expected raw byte length."""
    try:
        raw = base64.b64decode(value.encode("ascii"), validate=True)
    except (UnicodeEncodeError, ValueError) as exc:
        raise ValueError(f"{label} must be valid base64") from exc
    if len(raw) != expected_length:
        raise ValueError(f"{label} must decode to {expected_length} bytes")
    return raw


def public_key_id(public_key: Any) -> str:
    """Return a stable digest identifier for an Ed25519 public key."""
    return f"sha256:{sha256_bytes(raw_public_key(public_key))}"

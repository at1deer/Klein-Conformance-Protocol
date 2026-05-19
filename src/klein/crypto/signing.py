"""Ed25519 signing over Klein canonical JSON payload bytes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from klein.common.hashing import canonical_json_bytes
from klein.crypto.keys import (
    decode_base64_raw,
    encode_base64_raw,
    public_key_from_raw,
    raw_public_key,
)

SIGNATURE_ALGORITHM = "Ed25519"
PUBLIC_KEY_ENCODING = "base64.raw.ed25519"
SIGNATURE_ENCODING = "base64.raw.ed25519"


@dataclass(frozen=True)
class PayloadSignatureVerification:
    """Cryptographic verification status for one manifest signature."""

    ok: bool
    key_id: str | None = None
    error_code: str | None = None
    message: str | None = None


def signature_preimage(payload: dict[str, Any]) -> bytes:
    """Return the canonical JCS bytes signed by Run Manifest v1."""
    return canonical_json_bytes(payload)


def sign_payload(payload: dict[str, Any], private_key: Any, *, key_id: str) -> dict[str, str]:
    """Sign a manifest payload and return the Run Manifest v1 signature object."""
    public_key = private_key.public_key()
    signature = private_key.sign(signature_preimage(payload))
    return {
        "signature_algorithm": SIGNATURE_ALGORITHM,
        "key_id": key_id,
        "public_key_encoding": PUBLIC_KEY_ENCODING,
        "public_key": encode_base64_raw(raw_public_key(public_key)),
        "signature_encoding": SIGNATURE_ENCODING,
        "signature": encode_base64_raw(signature),
    }


def verify_payload_signature(
    payload: dict[str, Any],
    signature: dict[str, Any],
) -> PayloadSignatureVerification:
    """Verify one Run Manifest v1 signature object against a payload."""
    key_id = signature.get("key_id") if isinstance(signature.get("key_id"), str) else None
    if signature.get("signature_algorithm") != SIGNATURE_ALGORITHM:
        return PayloadSignatureVerification(
            ok=False,
            key_id=key_id,
            error_code="RUN_MANIFEST_SIGNATURE_INVALID",
            message="unsupported signature_algorithm",
        )
    if signature.get("public_key_encoding") != PUBLIC_KEY_ENCODING:
        return PayloadSignatureVerification(
            ok=False,
            key_id=key_id,
            error_code="RUN_MANIFEST_SIGNATURE_INVALID",
            message="unsupported public_key_encoding",
        )
    if signature.get("signature_encoding") != SIGNATURE_ENCODING:
        return PayloadSignatureVerification(
            ok=False,
            key_id=key_id,
            error_code="RUN_MANIFEST_SIGNATURE_INVALID",
            message="unsupported signature_encoding",
        )

    try:
        public_key = public_key_from_raw(
            decode_base64_raw(str(signature.get("public_key", "")), expected_length=32, label="public_key")
        )
        signature_bytes = decode_base64_raw(
            str(signature.get("signature", "")),
            expected_length=64,
            label="signature",
        )
        public_key.verify(signature_bytes, signature_preimage(payload))
    except Exception as exc:  # noqa: BLE001 - normalize crypto/base64 failures for callers.
        return PayloadSignatureVerification(
            ok=False,
            key_id=key_id,
            error_code="RUN_MANIFEST_SIGNATURE_INVALID",
            message=str(exc) or type(exc).__name__,
        )

    return PayloadSignatureVerification(ok=True, key_id=key_id)

"""Trust Policy v1 for signed Klein run manifests."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from klein.common.hashing import parse_ijson
from klein.crypto.keys import decode_base64_raw
from klein.crypto.registry import (
    BackendIdentityRegistry,
    BackendIdentityResolution,
    resolve_backend_identity,
)
from klein.crypto.signing import PUBLIC_KEY_ENCODING, SIGNATURE_ALGORITHM, SIGNATURE_ENCODING

TRUST_POLICY_VERSION = "klein.trust_policy.v1"


class TrustPolicyError(ValueError):
    """Structured Trust Policy v1 failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class TrustPolicyResult:
    """Authorization result for a cryptographically valid manifest signature."""

    trust_status: str
    trust_reason: str
    error_code: str | None = None
    key_id: str | None = None
    identity_status: str = "not_evaluated"
    backend_registry_id: str | None = None
    registry_backend_id: str | None = None
    registry_key_id: str | None = None
    registry_key_status: str | None = None
    registry_signed: bool = False
    registry_signature_status: str = "not_applicable"
    registry_provenance_status: str = "not_evaluated"
    registry_authority_id: str | None = None
    key_lifecycle_status: str | None = None

    @property
    def trusted(self) -> bool:
        return self.trust_status == "trusted"


def load_trust_policy(path: str | Path) -> dict[str, Any]:
    """Load a Trust Policy v1 JSON object."""
    try:
        policy = parse_ijson(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise TrustPolicyError("TRUST_POLICY_INVALID", f"trust policy JSON parse failed: {exc}") from exc
    if not isinstance(policy, dict):
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", "trust policy must be a JSON object")
    validate_trust_policy(policy)
    return policy


def validate_trust_policy(policy: dict[str, Any]) -> None:
    """Validate the minimal Trust Policy v1 shape enforced by the alpha tools."""
    if policy.get("policy_version") != TRUST_POLICY_VERSION:
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", "invalid policy_version")
    if not isinstance(policy.get("policy_id"), str) or not policy["policy_id"]:
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", "policy_id must be a non-empty string")
    trusted_keys = policy.get("trusted_keys")
    revoked_keys = policy.get("revoked_keys", [])
    trusted_registry_authorities = policy.get("trusted_registry_authorities", [])
    if not isinstance(trusted_keys, list):
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", "trusted_keys must be an array")
    if not isinstance(revoked_keys, list):
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", "revoked_keys must be an array")
    if not isinstance(trusted_registry_authorities, list):
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", "trusted_registry_authorities must be an array")
    for index, key in enumerate(trusted_keys):
        _validate_key_entry(key, f"trusted_keys[{index}]", require_scope=True)
    for index, key in enumerate(revoked_keys):
        _validate_key_entry(key, f"revoked_keys[{index}]", require_scope=False)
    for index, authority in enumerate(trusted_registry_authorities):
        _validate_registry_authority(authority, f"trusted_registry_authorities[{index}]")


def _validate_key_entry(entry: Any, location: str, *, require_scope: bool) -> None:
    if not isinstance(entry, dict):
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location} must be an object")
    for field in ("key_id", "signature_algorithm"):
        if not isinstance(entry.get(field), str) or not entry[field]:
            raise TrustPolicyError(
                "TRUST_POLICY_SCHEMA_INVALID",
                f"{location}.{field} must be a non-empty string",
            )
    source = entry.get("source")
    has_public_key = "public_key" in entry
    if source is not None and source != "registry":
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.source is invalid")
    if not has_public_key and source != "registry":
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.public_key is required unless source=registry")
    if has_public_key and (not isinstance(entry.get("public_key"), str) or not entry["public_key"]):
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.public_key must be a non-empty string")
    if has_public_key and not isinstance(entry.get("public_key_encoding"), str):
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.public_key_encoding must be a non-empty string")
    if has_public_key and entry["public_key_encoding"] != PUBLIC_KEY_ENCODING:
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location} has invalid public_key_encoding")
    if entry["signature_algorithm"] != SIGNATURE_ALGORITHM:
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location} has invalid signature_algorithm")
    if has_public_key:
        try:
            decode_base64_raw(entry["public_key"], expected_length=32, label=f"{location}.public_key")
        except ValueError as exc:
            raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", str(exc)) from exc
    if require_scope:
        scope = entry.get("trust_scope")
        if not isinstance(scope, dict):
            raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.trust_scope must be an object")
        for field in ("backend_ids", "profile_ids", "profile_versions", "manifest_versions"):
            values = scope.get(field)
            if not isinstance(values, list) or not values or not all(isinstance(v, str) for v in values):
                raise TrustPolicyError(
                    "TRUST_POLICY_SCHEMA_INVALID",
                    f"{location}.trust_scope.{field} must be a non-empty string array",
                )
        if entry.get("status") not in {"trusted", "disabled"}:
            raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.status is invalid")
    for field in ("not_before", "not_after"):
        value = entry.get(field)
        if value is not None and not isinstance(value, str):
            raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.{field} must be null or string")


def _validate_registry_authority(entry: Any, location: str) -> None:
    if not isinstance(entry, dict):
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location} must be an object")
    for field in ("authority_id", "public_key", "public_key_encoding", "signature_algorithm", "status"):
        if not isinstance(entry.get(field), str) or not entry[field]:
            raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.{field} must be a non-empty string")
    if entry["signature_algorithm"] != SIGNATURE_ALGORITHM:
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.signature_algorithm is invalid")
    if entry["public_key_encoding"] != PUBLIC_KEY_ENCODING:
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.public_key_encoding is invalid")
    try:
        decode_base64_raw(entry["public_key"], expected_length=32, label=f"{location}.public_key")
    except ValueError as exc:
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", str(exc)) from exc
    registry_ids = entry.get("registry_ids")
    if not isinstance(registry_ids, list) or not registry_ids or not all(isinstance(v, str) for v in registry_ids):
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.registry_ids must be a non-empty string array")
    if entry["status"] not in {"trusted", "disabled"}:
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.status is invalid")
    if entry.get("signature_encoding") not in {None, SIGNATURE_ENCODING}:
        raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.signature_encoding is invalid")
    for field in ("not_before", "not_after"):
        value = entry.get(field)
        if value is not None and not isinstance(value, str):
            raise TrustPolicyError("TRUST_POLICY_SCHEMA_INVALID", f"{location}.{field} must be null or string")


def evaluate_trust_policy(
    policy: dict[str, Any] | None,
    *,
    manifest: dict[str, Any],
    signature: dict[str, Any],
    backend_registry: BackendIdentityRegistry | dict[str, Any] | None = None,
    require_registry_provenance: bool = False,
) -> TrustPolicyResult:
    """Authorize a valid signature against a Trust Policy v1 document."""
    if policy is None:
        key_id = signature.get("key_id") if isinstance(signature.get("key_id"), str) else None
        return TrustPolicyResult(
            trust_status="not_evaluated",
            trust_reason="no_trust_policy",
            key_id=key_id,
        )
    validate_trust_policy(policy)

    key_id = str(signature.get("key_id", ""))
    public_key = str(signature.get("public_key", ""))
    identity = _resolve_identity(
        manifest,
        signature,
        backend_registry,
        policy=policy,
        require_registry_provenance=require_registry_provenance,
    )
    if identity is not None and not identity.ok:
        return _identity_result(identity, key_id)

    revoked = _matching_key(
        policy.get("revoked_keys", []),
        key_id=key_id,
        public_key=public_key,
        backend_registry=backend_registry,
        identity=identity,
    )
    if revoked is not None:
        return TrustPolicyResult(
            trust_status="untrusted",
            trust_reason="key_revoked",
            error_code="TRUST_POLICY_KEY_REVOKED",
            key_id=key_id,
        )

    trusted = _matching_key(
        policy["trusted_keys"],
        key_id=key_id,
        public_key=public_key,
        backend_registry=backend_registry,
        identity=identity,
    )
    if trusted is None:
        return TrustPolicyResult(
            trust_status="untrusted",
            trust_reason="key_not_found",
            error_code="TRUST_POLICY_KEY_NOT_FOUND",
            key_id=key_id,
        )
    if trusted.get("status") != "trusted":
        return TrustPolicyResult(
            trust_status="untrusted",
            trust_reason="key_not_trusted",
            error_code="BACKEND_IDENTITY_UNTRUSTED",
            key_id=key_id,
        )

    payload = manifest.get("payload", {})
    scope_mismatch = _scope_mismatch(policy_entry=trusted, manifest=manifest, payload=payload)
    if scope_mismatch is not None:
        return TrustPolicyResult(
            trust_status="untrusted",
            trust_reason=scope_mismatch,
            error_code="TRUST_POLICY_SCOPE_MISMATCH",
            key_id=key_id,
        )

    time_result = _time_status(trusted, payload)
    if time_result is not None:
        return TrustPolicyResult(
            trust_status=time_result[0],
            trust_reason=time_result[1],
            error_code=time_result[2],
            key_id=key_id,
        )

    return TrustPolicyResult(
        trust_status="trusted",
        trust_reason="policy_scope_match",
        key_id=key_id,
        identity_status=identity.identity_status if identity is not None else "not_evaluated",
        backend_registry_id=identity.backend_registry_id if identity is not None else None,
        registry_backend_id=identity.registry_backend_id if identity is not None else None,
        registry_key_id=identity.registry_key_id if identity is not None else None,
        registry_key_status=identity.registry_key_status if identity is not None else None,
        registry_signed=identity.registry_signed if identity is not None else False,
        registry_signature_status=identity.registry_signature_status if identity is not None else "not_applicable",
        registry_provenance_status=identity.registry_provenance_status if identity is not None else "not_evaluated",
        registry_authority_id=identity.registry_authority_id if identity is not None else None,
        key_lifecycle_status=identity.key_lifecycle_status if identity is not None else None,
    )


def _matching_key(
    keys: list[Any],
    *,
    key_id: str,
    public_key: str,
    backend_registry: BackendIdentityRegistry | dict[str, Any] | None = None,
    identity: BackendIdentityResolution | None = None,
) -> dict[str, Any] | None:
    for entry in keys:
        if not isinstance(entry, dict):
            continue
        if entry.get("key_id") != key_id:
            continue
        if entry.get("source") == "registry" and "public_key" not in entry and backend_registry is None:
            raise TrustPolicyError(
                "BACKEND_IDENTITY_REGISTRY_INVALID",
                "registry-backed trust policy entry requires a backend registry",
            )
        if entry.get("public_key") is not None and entry.get("public_key") != public_key:
            if identity is not None and entry.get("public_key") != identity.public_key:
                raise TrustPolicyError(
                    "BACKEND_IDENTITY_KEY_MISMATCH",
                    "trust policy public_key does not match registry public_key",
                )
            continue
        if "public_key" not in entry and entry.get("source") != "registry":
            continue
        if identity is not None and entry.get("public_key") not in {None, identity.public_key}:
            raise TrustPolicyError(
                "BACKEND_IDENTITY_KEY_MISMATCH",
                "trust policy public_key does not match registry public_key",
            )
        if "public_key" in entry or entry.get("source") == "registry":
            return entry
    return None


def _resolve_identity(
    manifest: dict[str, Any],
    signature: dict[str, Any],
    backend_registry: BackendIdentityRegistry | dict[str, Any] | None,
    *,
    policy: dict[str, Any],
    require_registry_provenance: bool,
) -> BackendIdentityResolution | None:
    if backend_registry is None:
        return None
    payload = manifest.get("payload", {})
    if not isinstance(payload, dict):
        return BackendIdentityResolution(
            identity_status="unresolved",
            error_code="BACKEND_IDENTITY_NOT_FOUND",
            message="manifest payload must be an object",
        )
    return resolve_backend_identity(
        payload,
        signature,
        backend_registry,
        trust_policy=policy,
        require_registry_provenance=require_registry_provenance,
    )


def _identity_result(identity: BackendIdentityResolution, key_id: str) -> TrustPolicyResult:
    return TrustPolicyResult(
        trust_status="untrusted",
        trust_reason=identity.message or "backend_identity_unresolved",
        error_code=identity.error_code or "BACKEND_IDENTITY_UNTRUSTED",
        key_id=key_id,
        identity_status=identity.identity_status,
        backend_registry_id=identity.backend_registry_id,
        registry_backend_id=identity.registry_backend_id,
        registry_key_id=identity.registry_key_id,
        registry_key_status=identity.registry_key_status,
        registry_signed=identity.registry_signed,
        registry_signature_status=identity.registry_signature_status,
        registry_provenance_status=identity.registry_provenance_status,
        registry_authority_id=identity.registry_authority_id,
        key_lifecycle_status=identity.key_lifecycle_status,
    )


def _scope_mismatch(
    *,
    policy_entry: dict[str, Any],
    manifest: dict[str, Any],
    payload: Any,
) -> str | None:
    if not isinstance(payload, dict):
        return "payload_not_object"
    scope = policy_entry["trust_scope"]
    checks = [
        ("backend_id", "backend_ids", payload.get("backend_id")),
        ("profile_id", "profile_ids", payload.get("profile_id")),
        ("profile_version", "profile_versions", payload.get("profile_version")),
        ("manifest_version", "manifest_versions", manifest.get("manifest_version")),
    ]
    for payload_field, scope_field, value in checks:
        if value not in scope[scope_field]:
            return f"{payload_field}_not_allowed"
    return None


def _time_status(entry: dict[str, Any], payload: dict[str, Any]) -> tuple[str, str, str | None] | None:
    not_before = entry.get("not_before")
    not_after = entry.get("not_after")
    if not_before is None and not_after is None:
        return None
    created_at = payload.get("created_at")
    if created_at is None:
        return ("indeterminate", "manifest_created_at_missing", None)
    if not isinstance(created_at, str):
        return ("untrusted", "manifest_created_at_invalid", "BACKEND_IDENTITY_UNTRUSTED")
    try:
        created = _parse_timestamp(created_at)
        if not_before is not None and created < _parse_timestamp(not_before):
            return ("untrusted", "manifest_before_key_validity", "BACKEND_IDENTITY_UNTRUSTED")
        if not_after is not None and created > _parse_timestamp(not_after):
            return ("untrusted", "manifest_after_key_validity", "BACKEND_IDENTITY_UNTRUSTED")
    except ValueError:
        return ("indeterminate", "time_validity_not_evaluated", None)
    return None


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)

"""Backend Identity Registry v1 validation and manifest identity resolution."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from klein.common.hashing import canonical_json_bytes, parse_ijson
from klein.crypto.keys import decode_base64_raw, public_key_from_raw
from klein.crypto.signing import PUBLIC_KEY_ENCODING, SIGNATURE_ALGORITHM, SIGNATURE_ENCODING

BACKEND_IDENTITY_REGISTRY_VERSION = "klein.backend_identity_registry.v1"


class BackendIdentityRegistryError(ValueError):
    """Structured Backend Identity Registry v1 failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class BackendIdentityRegistry:
    """Validated Backend Identity Registry v1 document."""

    data: dict[str, Any]
    raw: dict[str, Any] | None = None

    @property
    def registry_id(self) -> str:
        return str(self.data["registry_id"])

    @property
    def signed(self) -> bool:
        return self.raw is not None and isinstance(self.raw.get("payload"), dict)

    @property
    def signatures(self) -> list[Any]:
        if self.raw is None:
            return []
        signatures = self.raw.get("signatures", [])
        return signatures if isinstance(signatures, list) else []


@dataclass(frozen=True)
class RegistryProvenanceResult:
    """Signature/provenance result for Backend Identity Registry v1."""

    registry_id: str | None
    registry_signed: bool
    registry_signature_status: str
    registry_provenance_status: str
    registry_authority_id: str | None = None
    registry_error_code: str | None = None
    message: str | None = None

    @property
    def ok(self) -> bool:
        return self.registry_signature_status in {"valid", "not_applicable"} and self.registry_provenance_status in {
            "trusted",
            "not_evaluated",
        }


@dataclass(frozen=True)
class BackendIdentityResolution:
    """Resolved registry identity for a manifest signature."""

    identity_status: str
    backend_registry_id: str | None = None
    registry_backend_id: str | None = None
    registry_key_id: str | None = None
    registry_key_status: str | None = None
    public_key: str | None = None
    registry_signed: bool = False
    registry_signature_status: str = "not_applicable"
    registry_provenance_status: str = "not_evaluated"
    registry_authority_id: str | None = None
    key_lifecycle_status: str | None = None
    error_code: str | None = None
    message: str | None = None

    @property
    def ok(self) -> bool:
        return self.identity_status == "resolved"


def load_backend_identity_registry(path: str | Path) -> BackendIdentityRegistry:
    """Load and validate a Backend Identity Registry v1 JSON object."""
    try:
        registry = parse_ijson(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackendIdentityRegistryError(
            "BACKEND_IDENTITY_REGISTRY_INVALID",
            f"registry JSON parse failed: {exc}",
        ) from exc
    return validate_backend_identity_registry(registry)


def validate_backend_identity_registry(data: Any) -> BackendIdentityRegistry:
    """Validate the alpha Backend Identity Registry v1 shape."""
    if not isinstance(data, dict):
        raise BackendIdentityRegistryError(
            "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
            "registry must be a JSON object",
        )
    if data.get("registry_version") != BACKEND_IDENTITY_REGISTRY_VERSION:
        raise BackendIdentityRegistryError(
            "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
            "invalid registry_version",
        )
    raw = data
    if "payload" in data or "signatures" in data:
        payload = data.get("payload")
        if not isinstance(payload, dict):
            raise BackendIdentityRegistryError(
                "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
                "signed registry payload must be an object",
            )
        signatures = data.get("signatures")
        if not isinstance(signatures, list):
            raise BackendIdentityRegistryError(
                "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
                "signed registry signatures must be an array",
            )
        for index, signature in enumerate(signatures):
            _validate_registry_signature_shape(signature, f"signatures[{index}]")
        data = {"registry_version": raw["registry_version"], **payload}

    if not isinstance(data.get("registry_id"), str) or not data["registry_id"]:
        raise BackendIdentityRegistryError(
            "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
            "registry_id must be a non-empty string",
        )
    if not isinstance(data.get("description"), str):
        raise BackendIdentityRegistryError(
            "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
            "description must be a string",
        )
    if data.get("issued_at") is not None and not isinstance(data.get("issued_at"), str):
        raise BackendIdentityRegistryError(
            "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
            "issued_at must be null or string",
        )
    backends = data.get("backends")
    if not isinstance(backends, list) or not backends:
        raise BackendIdentityRegistryError(
            "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
            "backends must be a non-empty array",
        )
    backend_ids: set[str] = set()
    global_key_ids: set[str] = set()
    for index, backend in enumerate(backends):
        _validate_backend(backend, index, backend_ids, global_key_ids)
    return BackendIdentityRegistry(data=data, raw=raw)


def find_backend_key(
    registry: BackendIdentityRegistry | dict[str, Any],
    backend_id: str,
    key_id: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return `(backend, key)` for a registry backend/key pair."""
    data = registry.data if isinstance(registry, BackendIdentityRegistry) else registry
    for backend in data.get("backends", []):
        if isinstance(backend, dict) and backend.get("backend_id") == backend_id:
            for key in backend.get("keys", []):
                if isinstance(key, dict) and key.get("key_id") == key_id:
                    return backend, key
    return None


def resolve_backend_identity(
    manifest_payload: dict[str, Any],
    signature: dict[str, Any],
    registry: BackendIdentityRegistry | dict[str, Any],
    *,
    trust_policy: dict[str, Any] | None = None,
    require_registry_provenance: bool = False,
) -> BackendIdentityResolution:
    """Resolve manifest backend/key identity against a registry."""
    if not isinstance(registry, BackendIdentityRegistry):
        registry = validate_backend_identity_registry(registry)
    provenance = verify_backend_registry_signature(
        registry,
        trust_policy=trust_policy,
        require_trusted=require_registry_provenance,
    )
    if provenance.registry_signature_status == "invalid":
        return _resolution_error(
            provenance.registry_error_code or "BACKEND_REGISTRY_SIGNATURE_INVALID",
            provenance.message or "registry signature invalid",
            registry=registry,
            provenance=provenance,
        )
    if require_registry_provenance and provenance.registry_provenance_status != "trusted":
        return _resolution_error(
            provenance.registry_error_code or "BACKEND_REGISTRY_PROVENANCE_REQUIRED",
            provenance.message or "trusted signed registry provenance is required",
            registry=registry,
            provenance=provenance,
        )
    backend_id = _string(manifest_payload.get("backend_id"))
    backend_version = _string(manifest_payload.get("backend_version"))
    profile_id = _string(manifest_payload.get("profile_id"))
    profile_version = _string(manifest_payload.get("profile_version"))
    key_id = _string(signature.get("key_id"))
    public_key = _string(signature.get("public_key"))
    if backend_id is None or key_id is None:
        return _resolution_error(
            "BACKEND_IDENTITY_NOT_FOUND",
            "manifest backend_id and signature key_id are required",
            registry=registry,
            provenance=provenance,
        )

    match = find_backend_key(registry, backend_id, key_id)
    if match is None:
        backend_exists = any(
            isinstance(backend, dict) and backend.get("backend_id") == backend_id
            for backend in registry.data.get("backends", [])
        )
        code = "BACKEND_IDENTITY_KEY_NOT_FOUND" if backend_exists else "BACKEND_IDENTITY_NOT_FOUND"
        return _resolution_error(code, f"backend/key not found in registry: {backend_id}/{key_id}", registry=registry, provenance=provenance)
    backend, key = match
    if _listed(backend.get("backend_versions")) and backend_version not in backend["backend_versions"]:
        return _resolution_error("BACKEND_IDENTITY_SCOPE_MISMATCH", "backend_version is not declared by registry", registry=registry, provenance=provenance)
    if not _profile_allowed(backend, profile_id, profile_version):
        return _resolution_error("BACKEND_IDENTITY_SCOPE_MISMATCH", "profile is not declared by registry", registry=registry, provenance=provenance)
    if public_key is not None and public_key != key.get("public_key"):
        return _resolution_error("BACKEND_IDENTITY_KEY_MISMATCH", "manifest signature public_key does not match registry", registry=registry, provenance=provenance)
    lifecycle_status, lifecycle_code, lifecycle_message = _key_lifecycle_status(key, manifest_payload)
    status = _string(key.get("status"))
    if lifecycle_code is not None:
        return BackendIdentityResolution(
            identity_status="unresolved",
            backend_registry_id=registry.registry_id,
            registry_backend_id=backend_id,
            registry_key_id=key_id,
            registry_key_status=status,
            public_key=_string(key.get("public_key")),
            registry_signed=provenance.registry_signed,
            registry_signature_status=provenance.registry_signature_status,
            registry_provenance_status=provenance.registry_provenance_status,
            registry_authority_id=provenance.registry_authority_id,
            key_lifecycle_status=lifecycle_status,
            error_code=lifecycle_code,
            message=lifecycle_message,
        )
    return BackendIdentityResolution(
        identity_status="resolved",
        backend_registry_id=registry.registry_id,
        registry_backend_id=backend_id,
        registry_key_id=key_id,
        registry_key_status=status,
        public_key=_string(key.get("public_key")),
        registry_signed=provenance.registry_signed,
        registry_signature_status=provenance.registry_signature_status,
        registry_provenance_status=provenance.registry_provenance_status,
        registry_authority_id=provenance.registry_authority_id,
        key_lifecycle_status=lifecycle_status,
    )


def resolve_manifest_backend_identity(
    manifest_payload: dict[str, Any],
    signature: dict[str, Any],
    registry: BackendIdentityRegistry | dict[str, Any],
) -> BackendIdentityResolution:
    """Backward-compatible registry identity resolver."""
    return resolve_backend_identity(manifest_payload, signature, registry)


def verify_backend_registry_signature(
    registry: BackendIdentityRegistry | dict[str, Any],
    trust_policy: dict[str, Any] | None = None,
    *,
    require_trusted: bool = False,
) -> RegistryProvenanceResult:
    """Verify signed registry provenance against optional local authority trust roots."""
    if not isinstance(registry, BackendIdentityRegistry):
        registry = validate_backend_identity_registry(registry)
    if not registry.signed:
        return RegistryProvenanceResult(
            registry_id=registry.registry_id,
            registry_signed=False,
            registry_signature_status="missing" if require_trusted else "not_applicable",
            registry_provenance_status="untrusted" if require_trusted else "not_evaluated",
            registry_error_code="BACKEND_REGISTRY_PROVENANCE_REQUIRED" if require_trusted else None,
            message="registry is unsigned" if require_trusted else None,
        )
    signatures = registry.signatures
    if not signatures:
        return RegistryProvenanceResult(
            registry_id=registry.registry_id,
            registry_signed=True,
            registry_signature_status="missing",
            registry_provenance_status="untrusted" if require_trusted else "not_evaluated",
            registry_error_code="BACKEND_REGISTRY_SIGNATURE_MISSING",
            message="signed registry has no signatures",
        )
    trusted_authorities = _trusted_registry_authorities(trust_policy)
    first_valid: RegistryProvenanceResult | None = None
    for signature in signatures:
        authority_id = _string(signature.get("authority_id")) if isinstance(signature, dict) else None
        payload = registry.raw.get("payload", registry.data) if registry.raw is not None else registry.data
        signature_status, message = _verify_one_registry_signature(payload, signature)
        if signature_status != "valid":
            continue
        authority = _matching_authority(trusted_authorities, registry.registry_id, signature)
        if authority is not None:
            return RegistryProvenanceResult(
                registry_id=registry.registry_id,
                registry_signed=True,
                registry_signature_status="valid",
                registry_provenance_status="trusted",
                registry_authority_id=authority_id,
            )
        first_valid = RegistryProvenanceResult(
            registry_id=registry.registry_id,
            registry_signed=True,
            registry_signature_status="valid",
            registry_provenance_status="untrusted" if require_trusted else "not_evaluated",
            registry_authority_id=authority_id,
            registry_error_code="BACKEND_REGISTRY_AUTHORITY_UNTRUSTED" if require_trusted else None,
            message="registry signature authority is not trusted by policy" if require_trusted else None,
        )
    if first_valid is not None:
        return first_valid
    return RegistryProvenanceResult(
        registry_id=registry.registry_id,
        registry_signed=True,
        registry_signature_status="invalid",
        registry_provenance_status="untrusted",
        registry_authority_id=_string(signatures[0].get("authority_id")) if isinstance(signatures[0], dict) else None,
        registry_error_code="BACKEND_REGISTRY_SIGNATURE_INVALID",
        message=message if "message" in locals() else "no valid registry signature",
    )


def _validate_backend(backend: Any, index: int, backend_ids: set[str], global_key_ids: set[str]) -> None:
    location = f"backends[{index}]"
    if not isinstance(backend, dict):
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location} must be an object")
    backend_id = _required_string(backend, "backend_id", location)
    if backend_id in backend_ids:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", "backend_id values must be unique")
    backend_ids.add(backend_id)
    for field in ("backend_name", "backend_vendor"):
        _required_string(backend, field, location)
    _string_array(backend.get("backend_versions"), f"{location}.backend_versions", allow_empty=True)
    profiles = backend.get("profiles")
    if not isinstance(profiles, list):
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.profiles must be an array")
    for profile_index, profile in enumerate(profiles):
        _validate_profile(profile, f"{location}.profiles[{profile_index}]")
    keys = backend.get("keys")
    if not isinstance(keys, list) or not keys:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.keys must be non-empty")
    local_key_ids: set[str] = set()
    for key_index, key in enumerate(keys):
        _validate_key(key, f"{location}.keys[{key_index}]", local_key_ids, global_key_ids)
    for key_index, key in enumerate(keys):
        rotated_to = key.get("rotated_to") if isinstance(key, dict) else None
        if rotated_to is not None and rotated_to not in local_key_ids:
            raise BackendIdentityRegistryError(
                "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
                f"{location}.keys[{key_index}].rotated_to must reference a key in the same backend",
            )
    if not isinstance(backend.get("metadata"), dict):
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.metadata must be an object")


def _validate_profile(profile: Any, location: str) -> None:
    if not isinstance(profile, dict):
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location} must be an object")
    _required_string(profile, "profile_id", location)
    _string_array(profile.get("profile_versions"), f"{location}.profile_versions", allow_empty=True)


def _validate_key(key: Any, location: str, local_key_ids: set[str], global_key_ids: set[str]) -> None:
    if not isinstance(key, dict):
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location} must be an object")
    key_id = _required_string(key, "key_id", location)
    if key_id in local_key_ids or key_id in global_key_ids:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", "key_id values must be globally unique")
    local_key_ids.add(key_id)
    global_key_ids.add(key_id)
    if key.get("signature_algorithm") != SIGNATURE_ALGORITHM:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.signature_algorithm is invalid")
    if key.get("public_key_encoding") != PUBLIC_KEY_ENCODING:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.public_key_encoding is invalid")
    public_key = _required_string(key, "public_key", location)
    try:
        decode_base64_raw(public_key, expected_length=32, label=f"{location}.public_key")
    except ValueError as exc:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", str(exc)) from exc
    if key.get("status") not in {"active", "revoked", "retired"}:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.status is invalid")
    for field in ("not_before", "not_after", "revoked_at"):
        if key.get(field) is not None and not isinstance(key.get(field), str):
            raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.{field} must be null or string")
    if key.get("rotated_to") is not None and not isinstance(key.get("rotated_to"), str):
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.rotated_to must be null or string")
    if key.get("revocation_reason") is not None and not isinstance(key.get("revocation_reason"), str):
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.revocation_reason must be null or string")
    _required_string(key, "notes", location)


def _required_string(value: dict[str, Any], field: str, location: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.{field} must be a non-empty string")
    return result


def _string_array(value: Any, location: str, *, allow_empty: bool) -> None:
    if not isinstance(value, list) or (not allow_empty and not value) or not all(isinstance(item, str) for item in value):
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location} must be a string array")


def _profile_allowed(backend: dict[str, Any], profile_id: str | None, profile_version: str | None) -> bool:
    profiles = backend.get("profiles")
    if not isinstance(profiles, list) or not profiles:
        return True
    for profile in profiles:
        if not isinstance(profile, dict) or profile.get("profile_id") != profile_id:
            continue
        versions = profile.get("profile_versions")
        return not _listed(versions) or profile_version in versions
    return False


def _listed(value: Any) -> bool:
    return isinstance(value, list) and bool(value)


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _validate_registry_signature_shape(signature: Any, location: str) -> None:
    if not isinstance(signature, dict):
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location} must be an object")
    required = (
        "signature_algorithm",
        "authority_id",
        "public_key_encoding",
        "public_key",
        "signature_encoding",
        "signature",
    )
    for field in required:
        if not isinstance(signature.get(field), str) or not signature[field]:
            raise BackendIdentityRegistryError(
                "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID",
                f"{location}.{field} must be a non-empty string",
            )
    if signature["signature_algorithm"] != SIGNATURE_ALGORITHM:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.signature_algorithm is invalid")
    if signature["public_key_encoding"] != PUBLIC_KEY_ENCODING:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.public_key_encoding is invalid")
    if signature["signature_encoding"] != SIGNATURE_ENCODING:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", f"{location}.signature_encoding is invalid")
    try:
        decode_base64_raw(signature["public_key"], expected_length=32, label=f"{location}.public_key")
        decode_base64_raw(signature["signature"], expected_length=64, label=f"{location}.signature")
    except ValueError as exc:
        raise BackendIdentityRegistryError("BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID", str(exc)) from exc


def _verify_one_registry_signature(payload: dict[str, Any], signature: Any) -> tuple[str, str | None]:
    if not isinstance(signature, dict):
        return ("invalid", "registry signature must be an object")
    try:
        _validate_registry_signature_shape(signature, "signatures[]")
        public_key = public_key_from_raw(
            decode_base64_raw(str(signature.get("public_key", "")), expected_length=32, label="public_key")
        )
        signature_bytes = decode_base64_raw(
            str(signature.get("signature", "")),
            expected_length=64,
            label="signature",
        )
        public_key.verify(signature_bytes, canonical_json_bytes(payload))
    except Exception as exc:  # noqa: BLE001 - normalize crypto/base64 failures for callers.
        return ("invalid", str(exc) or type(exc).__name__)
    return ("valid", None)


def _trusted_registry_authorities(trust_policy: dict[str, Any] | None) -> list[Any]:
    if not isinstance(trust_policy, dict):
        return []
    authorities = trust_policy.get("trusted_registry_authorities", [])
    return authorities if isinstance(authorities, list) else []


def _matching_authority(authorities: list[Any], registry_id: str, signature: Any) -> dict[str, Any] | None:
    if not isinstance(signature, dict):
        return None
    for authority in authorities:
        if not isinstance(authority, dict):
            continue
        if authority.get("status") != "trusted":
            continue
        if authority.get("authority_id") != signature.get("authority_id"):
            continue
        if authority.get("public_key") != signature.get("public_key"):
            continue
        registry_ids = authority.get("registry_ids")
        if isinstance(registry_ids, list) and registry_id not in registry_ids:
            continue
        return authority
    return None


def _key_lifecycle_status(key: dict[str, Any], manifest_payload: dict[str, Any]) -> tuple[str, str | None, str | None]:
    status = _string(key.get("status"))
    if status == "revoked":
        return ("revoked", "BACKEND_IDENTITY_KEY_REVOKED", "registry key status is revoked")
    created_at = manifest_payload.get("created_at")
    if status == "retired" and created_at is None:
        return ("indeterminate", "BACKEND_IDENTITY_KEY_RETIRED", "retired registry key requires manifest created_at")
    if key.get("not_before") is not None or key.get("not_after") is not None or status == "retired":
        if not isinstance(created_at, str):
            return ("indeterminate", "BACKEND_IDENTITY_UNTRUSTED", "key validity requires manifest created_at")
        try:
            created = _parse_timestamp(created_at)
            not_before = key.get("not_before")
            not_after = key.get("not_after")
            if isinstance(not_before, str) and created < _parse_timestamp(not_before):
                return ("not_yet_valid", "BACKEND_IDENTITY_KEY_NOT_YET_VALID", "manifest predates registry key validity")
            if isinstance(not_after, str) and created > _parse_timestamp(not_after):
                code = "BACKEND_IDENTITY_KEY_RETIRED" if status == "retired" else "BACKEND_IDENTITY_KEY_EXPIRED"
                return ("expired", code, "manifest postdates registry key validity")
        except ValueError:
            return ("indeterminate", "BACKEND_IDENTITY_UNTRUSTED", "key validity could not parse manifest created_at")
    if status == "retired":
        return ("legacy_valid", None, None)
    if status == "active":
        return ("active", None, None)
    return ("untrusted", "BACKEND_IDENTITY_UNTRUSTED", f"registry key status is {status}")


def _parse_timestamp(value: str) -> datetime:
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _resolution_error(
    error_code: str,
    message: str,
    *,
    registry: BackendIdentityRegistry | None = None,
    provenance: RegistryProvenanceResult | None = None,
) -> BackendIdentityResolution:
    return BackendIdentityResolution(
        identity_status="unresolved",
        backend_registry_id=registry.registry_id if registry is not None else None,
        registry_signed=provenance.registry_signed if provenance is not None else False,
        registry_signature_status=provenance.registry_signature_status if provenance is not None else "not_applicable",
        registry_provenance_status=provenance.registry_provenance_status if provenance is not None else "not_evaluated",
        registry_authority_id=provenance.registry_authority_id if provenance is not None else None,
        error_code=error_code,
        message=message,
    )

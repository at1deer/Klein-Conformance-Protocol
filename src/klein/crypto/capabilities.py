"""Backend Capability Declaration v1 validation and verification."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.common.hashing import canonical_json_bytes, canonical_json_sha256_ref, parse_ijson
from klein.conformance.levels import verify_capability_declared_levels
from klein.crypto.keys import decode_base64_raw, public_key_from_raw
from klein.crypto.registry import (
    BackendIdentityRegistry,
    find_backend_key,
    validate_backend_identity_registry,
)
from klein.crypto.signing import PUBLIC_KEY_ENCODING, SIGNATURE_ALGORITHM, SIGNATURE_ENCODING
from klein.profiles.dmf.capabilities import validate_dmf_capabilities

CAPABILITY_DECLARATION_VERSION = "klein.backend_capability_declaration.v1"


class BackendCapabilityError(ValueError):
    """Structured Backend Capability Declaration v1 failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class BackendCapabilityVerification:
    """Verification result for a Backend Capability Declaration v1."""

    ok: bool
    signature_status: str = "not_evaluated"
    identity_status: str = "not_evaluated"
    trust_status: str = "not_evaluated"
    capability_scope_status: str = "not_evaluated"
    declaration_hash: str | None = None
    backend_id: str | None = None
    profile_id: str | None = None
    substrate_fingerprint: str | None = None
    error_code: str | None = None
    message: str | None = None


def load_backend_capability_declaration(path: str | Path) -> dict[str, Any]:
    """Load and validate a Backend Capability Declaration v1 JSON object."""
    try:
        declaration = parse_ijson(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BackendCapabilityError(
            "BACKEND_CAPABILITY_DECLARATION_INVALID",
            f"capability declaration JSON parse failed: {exc}",
        ) from exc
    validate_backend_capability_declaration(declaration)
    return declaration


def validate_backend_capability_declaration(data: Any, *, allow_target_claims: bool = False) -> None:
    """Validate the alpha Backend Capability Declaration v1 shape and DMF invariants."""
    if not isinstance(data, dict):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "declaration must be a JSON object")
    if data.get("capability_declaration_version") != CAPABILITY_DECLARATION_VERSION:
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "invalid capability_declaration_version")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload must be an object")
    signatures = data.get("signatures")
    if not isinstance(signatures, list) or not signatures:
        raise BackendCapabilityError("BACKEND_CAPABILITY_SIGNATURE_INVALID", "at least one signature is required")
    for field in ("declaration_id", "backend_id", "backend_version"):
        _required_string(payload, field, "payload")
    for field in ("issued_at", "not_before", "not_after"):
        if payload.get(field) is not None and not isinstance(payload.get(field), str):
            raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", f"payload.{field} must be null or string")
    _validate_profiles(payload.get("supported_profiles"))
    _string_array(payload.get("supported_conformance_levels"), "payload.supported_conformance_levels")
    level_result = verify_capability_declared_levels(data, allow_target_claims=allow_target_claims)
    if not level_result.ok:
        raise BackendCapabilityError(
            level_result.error_code or "CONFORMANCE_LEVEL_CLAIM_INVALID",
            level_result.message or "conformance level claim invalid",
        )
    _string_array(payload.get("supported_execution_modes"), "payload.supported_execution_modes")
    if not isinstance(payload.get("supported_hail_features"), dict):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload.supported_hail_features must be an object")
    if not isinstance(payload.get("supported_evidence_features"), dict):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload.supported_evidence_features must be an object")
    if not isinstance(payload.get("profile_capabilities"), dict):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload.profile_capabilities must be an object")
    _validate_hil_claim_requirements(payload)
    if not isinstance(payload.get("substrates"), list):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload.substrates must be an array")
    limitations = payload.get("limitations")
    if not isinstance(limitations, list) or not limitations or not all(isinstance(v, str) and v for v in limitations):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload.limitations must be a non-empty string array")
    for index, signature in enumerate(signatures):
        _validate_signature_shape(signature, f"signatures[{index}]")
    _validate_dmf_claim_requirements(payload)
    _validate_dmf(payload.get("profile_capabilities", {}).get("dmf"))


def verify_backend_capability_signature(
    declaration: dict[str, Any],
    registry: BackendIdentityRegistry | dict[str, Any] | None = None,
    trust_policy: dict[str, Any] | None = None,
    *,
    require_trust: bool = False,
) -> BackendCapabilityVerification:
    """Verify declaration signature and optional registry/trust binding."""
    try:
        validate_backend_capability_declaration(declaration)
    except BackendCapabilityError as exc:
        return _failure("invalid", "not_evaluated", "not_evaluated", "not_evaluated", exc.error_code, str(exc), declaration)
    payload = declaration["payload"]
    signature = declaration["signatures"][0]
    if not _verify_signature(payload, signature):
        return _failure("invalid", "not_evaluated", "not_evaluated", "not_evaluated", "BACKEND_CAPABILITY_SIGNATURE_INVALID", "capability signature invalid", declaration)
    identity_status = "not_evaluated"
    trust_status = "not_evaluated"
    if registry is not None:
        registry_obj = registry if isinstance(registry, BackendIdentityRegistry) else validate_backend_identity_registry(registry)
        match = find_backend_key(registry_obj, str(payload["backend_id"]), str(signature["key_id"]))
        if match is None:
            return _failure("valid", "unresolved", "not_evaluated", "not_evaluated", "BACKEND_IDENTITY_KEY_NOT_FOUND", "capability signing key not found in registry", declaration)
        _, key = match
        if key.get("public_key") != signature.get("public_key"):
            return _failure("valid", "unresolved", "not_evaluated", "not_evaluated", "BACKEND_IDENTITY_KEY_MISMATCH", "capability signing key does not match registry", declaration)
        if key.get("status") != "active":
            return _failure("valid", "unresolved", "not_evaluated", "not_evaluated", "BACKEND_IDENTITY_KEY_REVOKED", "capability signing key is not active", declaration)
        identity_status = "resolved"
    if trust_policy is not None:
        trust_status = "trusted" if _policy_trusts_capability_key(trust_policy, payload, signature) else "untrusted"
        if trust_status != "trusted" and require_trust:
            return _failure("valid", identity_status, trust_status, "not_evaluated", "BACKEND_CAPABILITY_UNTRUSTED", "capability signing key is not trusted by policy", declaration)
    return BackendCapabilityVerification(
        ok=True,
        signature_status="valid",
        identity_status=identity_status,
        trust_status=trust_status,
        capability_scope_status="not_evaluated",
        declaration_hash=capability_declaration_hash(declaration),
        backend_id=str(payload["backend_id"]),
    )


def verify_backend_capability_scope(
    declaration: dict[str, Any],
    *,
    backend_id: str,
    backend_version: str | None = None,
    profile_id: str,
    profile_version: str,
    mode: str,
    substrate_fingerprint: str | None = None,
) -> BackendCapabilityVerification:
    """Verify a declaration supports a concrete run scope."""
    try:
        validate_backend_capability_declaration(declaration)
    except BackendCapabilityError as exc:
        return _failure("not_evaluated", "not_evaluated", "not_evaluated", "fail", exc.error_code, str(exc), declaration)
    payload = declaration["payload"]
    if payload.get("backend_id") != backend_id:
        return _scope_failure("BACKEND_CAPABILITY_SCOPE_MISMATCH", "backend_id is not supported", declaration, profile_id, substrate_fingerprint)
    if backend_version is not None and payload.get("backend_version") != backend_version:
        return _scope_failure("BACKEND_CAPABILITY_SCOPE_MISMATCH", "backend_version is not supported", declaration, profile_id, substrate_fingerprint)
    if not _profile_supported(payload, profile_id, profile_version):
        return _scope_failure("BACKEND_CAPABILITY_PROFILE_UNSUPPORTED", "profile is not supported", declaration, profile_id, substrate_fingerprint)
    if mode not in payload.get("supported_execution_modes", []):
        return _scope_failure("BACKEND_CAPABILITY_MODE_UNSUPPORTED", "execution mode is not supported", declaration, profile_id, substrate_fingerprint)
    if substrate_fingerprint is not None:
        fingerprints = [
            substrate.get("substrate_fingerprint")
            for substrate in payload.get("substrates", [])
            if isinstance(substrate, dict)
        ]
        if substrate_fingerprint not in fingerprints:
            return _scope_failure("BACKEND_CAPABILITY_SUBSTRATE_MISMATCH", "substrate_fingerprint is not declared", declaration, profile_id, substrate_fingerprint)
    return BackendCapabilityVerification(
        ok=True,
        signature_status="not_evaluated",
        identity_status="not_evaluated",
        trust_status="not_evaluated",
        capability_scope_status="pass",
        declaration_hash=capability_declaration_hash(declaration),
        backend_id=backend_id,
        profile_id=profile_id,
        substrate_fingerprint=substrate_fingerprint,
    )


def capability_declaration_hash(declaration: dict[str, Any]) -> str:
    """Return the canonical SHA-256 hash of the declaration payload."""
    payload = declaration.get("payload")
    if not isinstance(payload, dict):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload must be an object")
    return canonical_json_sha256_ref(payload)


def verify_backend_capability_declaration(
    declaration: dict[str, Any],
    *,
    registry: BackendIdentityRegistry | dict[str, Any] | None = None,
    trust_policy: dict[str, Any] | None = None,
    backend_id: str | None = None,
    backend_version: str | None = None,
    profile_id: str | None = None,
    profile_version: str | None = None,
    mode: str | None = None,
    substrate_fingerprint: str | None = None,
    require_trust: bool = False,
) -> BackendCapabilityVerification:
    """Verify signature/trust and optional run scope in one call."""
    signature = verify_backend_capability_signature(
        declaration,
        registry=registry,
        trust_policy=trust_policy,
        require_trust=require_trust,
    )
    if not signature.ok:
        return signature
    if all(value is not None for value in (backend_id, profile_id, profile_version, mode)):
        scope = verify_backend_capability_scope(
            declaration,
            backend_id=str(backend_id),
            backend_version=backend_version,
            profile_id=str(profile_id),
            profile_version=str(profile_version),
            mode=str(mode),
            substrate_fingerprint=substrate_fingerprint,
        )
        if not scope.ok:
            return BackendCapabilityVerification(
                ok=False,
                signature_status=signature.signature_status,
                identity_status=signature.identity_status,
                trust_status=signature.trust_status,
                capability_scope_status=scope.capability_scope_status,
                declaration_hash=signature.declaration_hash,
                backend_id=signature.backend_id,
                profile_id=profile_id,
                substrate_fingerprint=substrate_fingerprint,
                error_code=scope.error_code,
                message=scope.message,
            )
        return BackendCapabilityVerification(
            ok=True,
            signature_status=signature.signature_status,
            identity_status=signature.identity_status,
            trust_status=signature.trust_status,
            capability_scope_status="pass",
            declaration_hash=signature.declaration_hash,
            backend_id=signature.backend_id,
            profile_id=profile_id,
            substrate_fingerprint=substrate_fingerprint,
        )
    return signature


def _verify_signature(payload: dict[str, Any], signature: dict[str, Any]) -> bool:
    try:
        public_key = public_key_from_raw(
            decode_base64_raw(str(signature.get("public_key", "")), expected_length=32, label="public_key")
        )
        signature_bytes = decode_base64_raw(str(signature.get("signature", "")), expected_length=64, label="signature")
        public_key.verify(signature_bytes, canonical_json_bytes(payload))
    except Exception:
        return False
    return True


def _policy_trusts_capability_key(policy: dict[str, Any], payload: dict[str, Any], signature: dict[str, Any]) -> bool:
    profile_ids = [profile.get("profile_id") for profile in payload.get("supported_profiles", []) if isinstance(profile, dict)]
    profile_versions = {
        version
        for profile in payload.get("supported_profiles", [])
        if isinstance(profile, dict)
        for version in profile.get("profile_versions", [])
        if isinstance(version, str)
    }
    for entry in policy.get("trusted_keys", []):
        if not isinstance(entry, dict) or entry.get("status") != "trusted":
            continue
        if entry.get("key_id") != signature.get("key_id"):
            continue
        if entry.get("public_key") not in {None, signature.get("public_key")}:
            continue
        scope = entry.get("trust_scope")
        if not isinstance(scope, dict):
            continue
        if payload.get("backend_id") not in scope.get("backend_ids", []):
            continue
        if not any(profile_id in scope.get("profile_ids", []) for profile_id in profile_ids):
            continue
        if not profile_versions.intersection(set(scope.get("profile_versions", []))):
            continue
        return True
    return False


def _validate_profiles(value: Any) -> None:
    if not isinstance(value, list) or not value:
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload.supported_profiles must be non-empty")
    for index, profile in enumerate(value):
        if not isinstance(profile, dict):
            raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", f"supported_profiles[{index}] must be an object")
        _required_string(profile, "profile_id", f"supported_profiles[{index}]")
        _required_string(profile, "profile_capability_set", f"supported_profiles[{index}]")
        _string_array(profile.get("profile_versions"), f"supported_profiles[{index}].profile_versions")


def _validate_dmf(value: Any) -> None:
    if value is None:
        return
    result = validate_dmf_capabilities(value)
    if not result.ok:
        raise BackendCapabilityError("DMF_CAPABILITIES_INVALID", result.message or "DMF capabilities invalid")


def _validate_dmf_claim_requirements(payload: dict[str, Any]) -> None:
    levels = set(payload.get("supported_conformance_levels", []))
    profile_caps = payload.get("profile_capabilities", {})
    dmf_caps = profile_caps.get("dmf") if isinstance(profile_caps, dict) else None
    claims_payload = "KCP-Profile-DMF-Payload-v1" in levels
    claims_sim = "KCP-Profile-DMF-Simulator-v1" in levels
    if (claims_payload or claims_sim) and dmf_caps is None:
        raise BackendCapabilityError(
            "DMF_CAPABILITIES_INVALID",
            "DMF conformance levels require profile_capabilities.dmf",
        )
    if claims_sim and not payload.get("substrates"):
        raise BackendCapabilityError(
            "DMF_SUBSTRATE_MISMATCH",
            "KCP-Profile-DMF-Simulator-v1 requires at least one declared substrate",
        )
    if dmf_caps is not None:
        payloads = dmf_caps.get("payloads", {}) if isinstance(dmf_caps, dict) else {}
        if claims_payload and "CHANNEL_LIST" not in payloads.get("supported_payload_kinds", []):
            raise BackendCapabilityError(
                "DMF_CAPABILITIES_INVALID",
                "KCP-Profile-DMF-Payload-v1 requires DMF payload support",
            )


def _validate_hil_claim_requirements(payload: dict[str, Any]) -> None:
    hil = payload.get("hil")
    levels = set(payload.get("supported_conformance_levels", []))
    if hil is None:
        if "KCP-Core-HIL-Readiness-v1" in levels or "KCP-Profile-DMF-HIL-L0" in levels:
            raise BackendCapabilityError("HIL_CONTRACT_INVALID", "HIL readiness levels require payload.hil")
        return
    if not isinstance(hil, dict):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload.hil must be an object")
    if hil.get("hardware_execution_supported") is True or hil.get("hardware_attestation_supported") is True:
        raise BackendCapabilityError("HIL_HARDWARE_CLAIM_UNSUPPORTED", "hardware execution and attestation are not supported in CURRENT_ALPHA")
    levels_supported = hil.get("hil_levels_supported")
    if not isinstance(levels_supported, list) or not all(isinstance(level, str) and level for level in levels_supported):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", "payload.hil.hil_levels_supported must be a string array")
    if "KCP-Profile-DMF-HIL-L1" in levels_supported:
        raise BackendCapabilityError("HIL_HARDWARE_CLAIM_UNSUPPORTED", "HIL-L1 cannot be declared supported in CURRENT_ALPHA")
    contract_hash = hil.get("hil_contract_hash")
    if (hil.get("hil_readiness") is True or levels_supported) and not (isinstance(contract_hash, str) and contract_hash.startswith("sha256:") and len(contract_hash) == 71):
        raise BackendCapabilityError("HIL_CONTRACT_INVALID", "HIL readiness requires hil_contract_hash")
    if "KCP-Profile-DMF-HIL-L0" in levels and "KCP-Profile-DMF-HIL-L0" not in levels_supported:
        raise BackendCapabilityError("HIL_CONTRACT_INVALID", "KCP-Profile-DMF-HIL-L0 requires payload.hil.hil_levels_supported")


def _validate_signature_shape(signature: Any, location: str) -> None:
    if not isinstance(signature, dict):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", f"{location} must be an object")
    for field in ("signature_algorithm", "key_id", "public_key_encoding", "public_key", "signature_encoding", "signature"):
        if not isinstance(signature.get(field), str) or not signature[field]:
            raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", f"{location}.{field} must be a non-empty string")
    if signature["signature_algorithm"] != SIGNATURE_ALGORITHM:
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", f"{location}.signature_algorithm is invalid")
    if signature["public_key_encoding"] != PUBLIC_KEY_ENCODING:
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", f"{location}.public_key_encoding is invalid")
    if signature["signature_encoding"] != SIGNATURE_ENCODING:
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", f"{location}.signature_encoding is invalid")
    decode_base64_raw(signature["public_key"], expected_length=32, label=f"{location}.public_key")
    decode_base64_raw(signature["signature"], expected_length=64, label=f"{location}.signature")


def _profile_supported(payload: dict[str, Any], profile_id: str, profile_version: str) -> bool:
    for profile in payload.get("supported_profiles", []):
        if isinstance(profile, dict) and profile.get("profile_id") == profile_id and profile_version in profile.get("profile_versions", []):
            return True
    return False


def _required_string(value: dict[str, Any], field: str, location: str) -> str:
    result = value.get(field)
    if not isinstance(result, str) or not result:
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", f"{location}.{field} must be a non-empty string")
    return result


def _string_array(value: Any, location: str) -> None:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item for item in value):
        raise BackendCapabilityError("BACKEND_CAPABILITY_SCHEMA_INVALID", f"{location} must be a non-empty string array")


def _failure(
    signature_status: str,
    identity_status: str,
    trust_status: str,
    scope_status: str,
    error_code: str,
    message: str,
    declaration: dict[str, Any],
) -> BackendCapabilityVerification:
    payload = declaration.get("payload", {}) if isinstance(declaration, dict) else {}
    return BackendCapabilityVerification(
        ok=False,
        signature_status=signature_status,
        identity_status=identity_status,
        trust_status=trust_status,
        capability_scope_status=scope_status,
        declaration_hash=capability_declaration_hash(declaration) if isinstance(payload, dict) else None,
        backend_id=payload.get("backend_id") if isinstance(payload.get("backend_id"), str) else None,
        error_code=error_code,
        message=message,
    )


def _scope_failure(
    error_code: str,
    message: str,
    declaration: dict[str, Any],
    profile_id: str,
    substrate_fingerprint: str | None,
) -> BackendCapabilityVerification:
    payload = declaration["payload"]
    return BackendCapabilityVerification(
        ok=False,
        signature_status="not_evaluated",
        identity_status="not_evaluated",
        trust_status="not_evaluated",
        capability_scope_status="fail",
        declaration_hash=capability_declaration_hash(declaration),
        backend_id=payload.get("backend_id") if isinstance(payload.get("backend_id"), str) else None,
        profile_id=profile_id,
        substrate_fingerprint=substrate_fingerprint,
        error_code=error_code,
        message=message,
    )

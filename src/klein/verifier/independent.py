"""Language-neutral independent verifier contract for KCP Run Bundle v1."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from klein.bundle.verify import verify_run_bundle

INDEPENDENT_VERIFIER_RESULT_VERSION = "klein.independent_verifier_result.v1"


@dataclass
class IndependentVerifierResult:
    """Top-level result for independent `.kcprun` verification."""

    overall_status: str
    bundle_format: str | None
    bundle_path: str
    checks: dict[str, str]
    bindings: dict[str, Any]
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.overall_status == "pass"

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_version": INDEPENDENT_VERIFIER_RESULT_VERSION,
            "overall_status": self.overall_status,
            "bundle_format": self.bundle_format,
            "bundle_path": self.bundle_path,
            "checks": self.checks,
            "bindings": self.bindings,
            "errors": self.errors,
            "warnings": self.warnings,
        }


def verify_bundle_independently(
    bundle_path: Path,
    *,
    backend_registry_path: Path | None = None,
    require_signed_registry: bool = False,
    require_backend_capabilities: bool = False,
) -> IndependentVerifierResult:
    """Verify a bundle without simulator, vector metadata, or conformance-runner state."""
    bundle_result = verify_run_bundle(
        bundle_path,
        backend_registry_path=backend_registry_path,
        require_signed_registry=require_signed_registry,
        require_backend_capabilities=require_backend_capabilities,
    )
    signed = bundle_result.signed_conformance_result or {}
    signed_checks = signed.get("checks", {}) if isinstance(signed.get("checks"), dict) else {}

    checks = {
        "bundle_schema": bundle_result.bundle_schema_status,
        "bundle_entry_hashes": bundle_result.bundle_entry_hash_status,
        "hail_schema": _signed_check(signed_checks, "hail_schema_status", bundle_result),
        "hail_canonicalization": _signed_check(
            signed_checks,
            "canonicalization_status",
            bundle_result,
        ),
        "hail_ordering": _signed_check(signed_checks, "canonicalization_status", bundle_result),
        "hail_lifecycle": _signed_check(signed_checks, "lifecycle_status", bundle_result),
        "hail_chain": _signed_check(signed_checks, "chain_status", bundle_result),
        "run_manifest_schema": _signed_check(
            signed_checks,
            "manifest_schema_status",
            bundle_result,
        ),
        "run_manifest_payload": _signed_check(
            signed_checks,
            "manifest_payload_status",
            bundle_result,
        ),
        "run_manifest_signature": _signed_check(signed_checks, "signature_status", bundle_result),
        "trust_policy_schema": _trust_policy_schema_status(signed, bundle_result),
        "trust_policy_authorization": _signed_check(signed_checks, "trust_status", bundle_result),
        "backend_identity_registry": _signed_check(
            signed_checks,
            "backend_identity_registry_status",
            bundle_result,
        ),
        "backend_identity_resolution": _signed_check(
            signed_checks,
            "backend_identity_resolution_status",
            bundle_result,
        ),
        "conformance_report": _signed_check(signed_checks, "report_binding_status", bundle_result),
    }
    bindings = {
        "artifact_hash": bundle_result.artifact_hash,
        "hail_digest": bundle_result.hail_digest,
        "hail_chain_digest": bundle_result.hail_chain_digest,
        "backend_id": bundle_result.backend_id,
        "backend_version": _payload_field(signed, "backend_version"),
        "profile_id": bundle_result.profile_id,
        "profile_version": _payload_field(signed, "profile_version"),
        "substrate_fingerprint": bundle_result.substrate_fingerprint,
        "trusted_key_ids": _trusted_key_ids(signed),
        "identity_status": signed.get("identity_status") if isinstance(signed.get("identity_status"), str) else "not_evaluated",
        "backend_registry_id": signed.get("backend_registry_id") if isinstance(signed.get("backend_registry_id"), str) else None,
        "backend_registry_hash": bundle_result.backend_registry_hash,
        "backend_identity_status": signed.get("backend_identity_status")
        if isinstance(signed.get("backend_identity_status"), str)
        else "not_evaluated",
        "backend_key_status": signed.get("backend_key_status") if isinstance(signed.get("backend_key_status"), str) else None,
        "registry_key_id": signed.get("registry_key_id") if isinstance(signed.get("registry_key_id"), str) else None,
        "registry_backend_id": signed.get("registry_backend_id") if isinstance(signed.get("registry_backend_id"), str) else None,
        "registry_signed": bool(signed.get("registry_signed")),
        "registry_signature_status": signed.get("registry_signature_status")
        if isinstance(signed.get("registry_signature_status"), str)
        else "not_applicable",
        "registry_provenance_status": signed.get("registry_provenance_status")
        if isinstance(signed.get("registry_provenance_status"), str)
        else "not_evaluated",
        "registry_authority_id": signed.get("registry_authority_id") if isinstance(signed.get("registry_authority_id"), str) else None,
        "key_lifecycle_status": signed.get("key_lifecycle_status") if isinstance(signed.get("key_lifecycle_status"), str) else None,
        "backend_capabilities_present": bundle_result.backend_capabilities_present,
        "backend_capability_declaration_hash": bundle_result.backend_capability_declaration_hash,
        "backend_capability_signature_status": bundle_result.backend_capability_signature_status,
        "backend_capability_trust_status": bundle_result.backend_capability_trust_status,
        "backend_capability_scope_status": bundle_result.backend_capability_scope_status,
        "backend_capability_error_code": bundle_result.backend_capability_error_code,
        "declared_conformance_levels": bundle_result.declared_conformance_levels,
        "verified_conformance_levels": bundle_result.verified_conformance_levels,
        "conformance_level_catalog_status": bundle_result.conformance_level_catalog_status,
        "conformance_level_dependency_status": bundle_result.conformance_level_dependency_status,
        "conformance_level_error_code": bundle_result.conformance_level_error_code,
    }
    return IndependentVerifierResult(
        overall_status="pass" if _all_required_pass(checks) else "fail",
        bundle_format=bundle_result.bundle_format,
        bundle_path=str(bundle_path),
        checks=checks,
        bindings=bindings,
        errors=_independent_errors(bundle_result, signed),
        warnings=bundle_result.warnings,
    )


def _signed_check(
    signed_checks: dict[str, Any],
    name: str,
    bundle_result: Any,
) -> str:
    if bundle_result.bundle_entry_hash_status != "pass":
        return "not_evaluated"
    value = signed_checks.get(name)
    return value if value in {"pass", "fail", "not_applicable", "not_evaluated"} else "not_evaluated"


def _trust_policy_schema_status(signed: dict[str, Any], bundle_result: Any) -> str:
    if bundle_result.bundle_entry_hash_status != "pass":
        return "not_evaluated"
    errors = signed.get("errors", []) if isinstance(signed.get("errors"), list) else []
    if any(error.get("error_code") == "TRUST_POLICY_SCHEMA_INVALID" for error in errors if isinstance(error, dict)):
        return "fail"
    return "pass" if signed else "not_evaluated"


def _payload_field(signed: dict[str, Any], field_name: str) -> str | None:
    # The signed-conformance result intentionally exposes only stable binding fields.
    bindings = {
        "backend_version": None,
        "profile_version": signed.get("profile_version") if isinstance(signed.get("profile_version"), str) else None,
    }
    return bindings.get(field_name)


def _trusted_key_ids(signed: dict[str, Any]) -> list[str]:
    values = signed.get("trusted_key_ids", [])
    return [value for value in values if isinstance(value, str)] if isinstance(values, list) else []


def _independent_errors(bundle_result: Any, signed: dict[str, Any]) -> list[dict[str, Any]]:
    signed_errors = signed.get("errors", []) if isinstance(signed.get("errors"), list) else []
    normalized_signed = [
        error for error in signed_errors if isinstance(error, dict) and "error_code" in error
    ]
    if normalized_signed:
        return normalized_signed + bundle_result.errors
    return bundle_result.errors


def _all_required_pass(checks: dict[str, str]) -> bool:
    return all(
        status == "pass"
        for name, status in checks.items()
        if name not in {"conformance_report", "backend_identity_registry", "backend_identity_resolution"}
        or status != "not_applicable"
    )

"""Structured signed-conformance verifier result."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

SIGNED_CONFORMANCE_RESULT_VERSION = "klein.signed_conformance_result.v1"


@dataclass
class SignedConformanceResult:
    """Machine-readable result for KCP-Core-Signed-Conformance-v1 verification."""

    overall_status: str = "fail"
    hail_schema_status: str = "not_evaluated"
    canonicalization_status: str = "not_evaluated"
    lifecycle_status: str = "not_evaluated"
    chain_status: str = "not_evaluated"
    manifest_schema_status: str = "not_evaluated"
    manifest_payload_status: str = "not_evaluated"
    signature_status: str = "not_evaluated"
    trust_status: str = "not_evaluated"
    backend_identity_registry_status: str = "not_applicable"
    backend_identity_resolution_status: str = "not_applicable"
    artifact_binding_status: str = "not_evaluated"
    report_binding_status: str = "not_evaluated"
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    hail_digest: str | None = None
    hail_chain_digest: str | None = None
    manifest_key_ids: list[str] = field(default_factory=list)
    trusted_key_ids: list[str] = field(default_factory=list)
    backend_id: str | None = None
    profile_id: str | None = None
    profile_version: str | None = None
    artifact_hash: str | None = None
    substrate_fingerprint: str | None = None
    identity_status: str = "not_evaluated"
    backend_registry_id: str | None = None
    backend_registry_hash: str | None = None
    backend_identity_status: str = "not_evaluated"
    backend_key_status: str | None = None
    registry_key_id: str | None = None
    registry_backend_id: str | None = None
    registry_signed: bool = False
    registry_signature_status: str = "not_applicable"
    registry_provenance_status: str = "not_evaluated"
    registry_authority_id: str | None = None
    key_lifecycle_status: str | None = None

    @property
    def ok(self) -> bool:
        return self.overall_status == "pass"

    def add_error(self, error_code: str, message: str, *, check: str) -> None:
        self.errors.append({"check": check, "error_code": error_code, "message": message})

    def add_warning(self, message: str, *, check: str, code: str | None = None) -> None:
        warning: dict[str, Any] = {"check": check, "message": message}
        if code is not None:
            warning["code"] = code
        self.warnings.append(warning)

    def to_dict(self) -> dict[str, Any]:
        return {
            "result_version": SIGNED_CONFORMANCE_RESULT_VERSION,
            "overall_status": self.overall_status,
            "checks": {
                "hail_schema_status": self.hail_schema_status,
                "canonicalization_status": self.canonicalization_status,
                "lifecycle_status": self.lifecycle_status,
                "chain_status": self.chain_status,
                "manifest_schema_status": self.manifest_schema_status,
                "manifest_payload_status": self.manifest_payload_status,
                "signature_status": self.signature_status,
                "trust_status": self.trust_status,
                "backend_identity_registry_status": self.backend_identity_registry_status,
                "backend_identity_resolution_status": self.backend_identity_resolution_status,
                "artifact_binding_status": self.artifact_binding_status,
                "report_binding_status": self.report_binding_status,
            },
            "errors": self.errors,
            "warnings": self.warnings,
            "hail_digest": self.hail_digest,
            "hail_chain_digest": self.hail_chain_digest,
            "manifest_key_ids": self.manifest_key_ids,
            "trusted_key_ids": self.trusted_key_ids,
            "backend_id": self.backend_id,
            "profile_id": self.profile_id,
            "profile_version": self.profile_version,
            "artifact_hash": self.artifact_hash,
            "substrate_fingerprint": self.substrate_fingerprint,
            "identity_status": self.identity_status,
            "backend_registry_id": self.backend_registry_id,
            "backend_registry_hash": self.backend_registry_hash,
            "backend_identity_status": self.backend_identity_status,
            "backend_key_status": self.backend_key_status,
            "registry_key_id": self.registry_key_id,
            "registry_backend_id": self.registry_backend_id,
            "registry_signed": self.registry_signed,
            "registry_signature_status": self.registry_signature_status,
            "registry_provenance_status": self.registry_provenance_status,
            "registry_authority_id": self.registry_authority_id,
            "key_lifecycle_status": self.key_lifecycle_status,
        }

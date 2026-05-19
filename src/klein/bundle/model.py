"""KCP Run Bundle v1 models and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

RUN_BUNDLE_VERSION = "klein.run_bundle.v1"
RUN_BUNDLE_RESULT_VERSION = "klein.run_bundle_result.v1"
RUN_BUNDLE_EXTENSION = ".kcprun"

REQUIRED_ENTRY_KEYS = ("artifact", "hail", "run_manifest", "trust_policy")
OPTIONAL_ENTRY_KEYS = (
    "conformance_report",
    "signed_conformance_report",
    "backend_registry",
    "backend_capabilities",
)
ALL_ENTRY_KEYS = REQUIRED_ENTRY_KEYS + OPTIONAL_ENTRY_KEYS
_SHA256_REF_RE = re.compile(r"^sha256:[a-f0-9]{64}$")


class RunBundleError(ValueError):
    """Structured KCP Run Bundle v1 failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class RunBundle:
    """Parsed Run Bundle v1 manifest."""

    bundle: dict[str, Any]

    @property
    def entries(self) -> dict[str, str | None]:
        return self.bundle["entries"]

    @property
    def hashes(self) -> dict[str, str | None]:
        return self.bundle["hashes"]


@dataclass
class RunBundleResult:
    """Machine-readable result for KCP Run Bundle v1 verification."""

    bundle_path: str | None = None
    bundle_format: str | None = None
    overall_status: str = "fail"
    bundle_schema_status: str = "not_evaluated"
    bundle_entry_hash_status: str = "not_evaluated"
    signed_conformance_status: str = "not_evaluated"
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    signed_conformance_result: dict[str, Any] | None = None
    bundle_hashes: dict[str, str | None] = field(default_factory=dict)
    resolved_paths: dict[str, str | None] = field(default_factory=dict)
    hail_digest: str | None = None
    hail_chain_digest: str | None = None
    run_manifest_key_ids: list[str] = field(default_factory=list)
    trust_status: str = "not_evaluated"
    backend_id: str | None = None
    profile_id: str | None = None
    artifact_hash: str | None = None
    artifact_type: str | None = None
    artifact_schema_status: str = "not_evaluated"
    artifact_canonicalization: str | None = None
    artifact_validation_error_code: str | None = None
    substrate_fingerprint: str | None = None
    backend_registry_hash: str | None = None
    registry_signed: bool = False
    registry_signature_status: str = "not_applicable"
    registry_provenance_status: str = "not_evaluated"
    registry_authority_id: str | None = None
    key_lifecycle_status: str | None = None
    backend_capabilities_present: bool = False
    backend_capability_declaration_hash: str | None = None
    backend_capability_signature_status: str = "not_evaluated"
    backend_capability_trust_status: str = "not_evaluated"
    backend_capability_scope_status: str = "not_evaluated"
    backend_capability_error_code: str | None = None
    declared_conformance_levels: list[str] = field(default_factory=list)
    verified_conformance_levels: list[str] = field(default_factory=list)
    conformance_level_catalog_status: str = "not_evaluated"
    conformance_level_dependency_status: str = "not_evaluated"
    conformance_level_error_code: str | None = None

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
            "result_version": RUN_BUNDLE_RESULT_VERSION,
            "overall_status": self.overall_status,
            "bundle_path": self.bundle_path,
            "bundle_format": self.bundle_format,
            "checks": {
                "bundle_schema_status": self.bundle_schema_status,
                "bundle_entry_hash_status": self.bundle_entry_hash_status,
                "artifact_schema_status": self.artifact_schema_status,
                "signed_conformance_status": self.signed_conformance_status,
            },
            "errors": self.errors,
            "warnings": self.warnings,
            "signed_conformance_result": self.signed_conformance_result,
            "bundle_hashes": self.bundle_hashes,
            "resolved_paths": self.resolved_paths,
            "hail_digest": self.hail_digest,
            "hail_chain_digest": self.hail_chain_digest,
            "run_manifest_key_ids": self.run_manifest_key_ids,
            "trust_status": self.trust_status,
            "backend_id": self.backend_id,
            "profile_id": self.profile_id,
            "artifact_hash": self.artifact_hash,
            "artifact_type": self.artifact_type,
            "artifact_schema_status": self.artifact_schema_status,
            "artifact_canonicalization": self.artifact_canonicalization,
            "artifact_validation_error_code": self.artifact_validation_error_code,
            "substrate_fingerprint": self.substrate_fingerprint,
            "backend_registry_hash": self.backend_registry_hash,
            "registry_signed": self.registry_signed,
            "registry_signature_status": self.registry_signature_status,
            "registry_provenance_status": self.registry_provenance_status,
            "registry_authority_id": self.registry_authority_id,
            "key_lifecycle_status": self.key_lifecycle_status,
            "backend_capabilities_present": self.backend_capabilities_present,
            "backend_capability_declaration_hash": self.backend_capability_declaration_hash,
            "backend_capability_signature_status": self.backend_capability_signature_status,
            "backend_capability_trust_status": self.backend_capability_trust_status,
            "backend_capability_scope_status": self.backend_capability_scope_status,
            "backend_capability_error_code": self.backend_capability_error_code,
            "declared_conformance_levels": self.declared_conformance_levels,
            "verified_conformance_levels": self.verified_conformance_levels,
            "conformance_level_catalog_status": self.conformance_level_catalog_status,
            "conformance_level_dependency_status": self.conformance_level_dependency_status,
            "conformance_level_error_code": self.conformance_level_error_code,
        }


def validate_bundle_path(value: Any, *, field: str) -> str | None:
    """Validate a portable bundle-relative path."""
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RunBundleError("RUN_BUNDLE_SCHEMA_INVALID", f"{field} must be a non-empty string or null")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
        raise RunBundleError(
            "RUN_BUNDLE_SCHEMA_INVALID",
            f"{field} must be a portable relative path inside the bundle",
        )
    return value


def validate_run_bundle_structure(bundle: Any) -> RunBundle:
    """Validate the minimal Run Bundle v1 manifest structure used by tools."""
    if not isinstance(bundle, dict):
        raise RunBundleError("RUN_BUNDLE_SCHEMA_INVALID", "bundle.json must be a JSON object")
    allowed_top_level = {"bundle_version", "bundle_id", "created_by", "created_at", "entries", "hashes"}
    unknown_top_level = sorted(set(bundle) - allowed_top_level)
    if unknown_top_level:
        raise RunBundleError(
            "RUN_BUNDLE_SCHEMA_INVALID",
            f"bundle.json has unknown field(s): {', '.join(unknown_top_level)}",
        )
    if bundle.get("bundle_version") != RUN_BUNDLE_VERSION:
        raise RunBundleError("RUN_BUNDLE_SCHEMA_INVALID", "invalid bundle_version")
    entries = bundle.get("entries")
    hashes = bundle.get("hashes")
    if not isinstance(entries, dict):
        raise RunBundleError("RUN_BUNDLE_SCHEMA_INVALID", "entries must be an object")
    if not isinstance(hashes, dict):
        raise RunBundleError("RUN_BUNDLE_SCHEMA_INVALID", "hashes must be an object")
    unknown_entries = sorted(set(entries) - set(ALL_ENTRY_KEYS))
    unknown_hashes = sorted(set(hashes) - set(ALL_ENTRY_KEYS))
    if unknown_entries:
        raise RunBundleError(
            "RUN_BUNDLE_SCHEMA_INVALID",
            f"entries has unknown field(s): {', '.join(unknown_entries)}",
        )
    if unknown_hashes:
        raise RunBundleError(
            "RUN_BUNDLE_SCHEMA_INVALID",
            f"hashes has unknown field(s): {', '.join(unknown_hashes)}",
        )
    for top_level_field in ("bundle_id", "created_by", "created_at"):
        if bundle.get(top_level_field) is not None and not isinstance(bundle.get(top_level_field), str):
            raise RunBundleError("RUN_BUNDLE_SCHEMA_INVALID", f"{top_level_field} must be string or null")
    if bundle.get("created_by") is None:
        raise RunBundleError("RUN_BUNDLE_SCHEMA_INVALID", "created_by is required")

    for key in REQUIRED_ENTRY_KEYS:
        path = validate_bundle_path(entries.get(key), field=f"entries.{key}")
        if path is None:
            raise RunBundleError("RUN_BUNDLE_MISSING_ENTRY", f"entries.{key} is required")
    for key in OPTIONAL_ENTRY_KEYS:
        validate_bundle_path(entries.get(key), field=f"entries.{key}")
    for key in ALL_ENTRY_KEYS:
        value = hashes.get(key)
        if key in REQUIRED_ENTRY_KEYS and value is None:
            raise RunBundleError("RUN_BUNDLE_SCHEMA_INVALID", f"hashes.{key} is required")
        if value is not None and (not isinstance(value, str) or not _SHA256_REF_RE.match(value)):
            raise RunBundleError(
                "RUN_BUNDLE_SCHEMA_INVALID",
                f"hashes.{key} must be sha256:<hex> or null",
            )
    return RunBundle(bundle=bundle)


def declared_entry_paths(bundle: RunBundle) -> set[str]:
    """Return all non-null paths declared by bundle.json."""
    return {path for path in bundle.entries.values() if isinstance(path, str)}

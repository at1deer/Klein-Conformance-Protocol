"""Verify and inspect KCP Run Bundle v1 artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from klein.artifacts import ArtifactValidationError, canonical_artifact_hash, validate_artifact
from klein.bundle.archive import load_bundle_source
from klein.bundle.model import RunBundle, RunBundleError, RunBundleResult
from klein.common.hashing import raw_file_sha256
from klein.conformance.levels import verify_capability_declared_levels
from klein.crypto.capabilities import (
    BackendCapabilityError,
    load_backend_capability_declaration,
    verify_backend_capability_declaration,
)
from klein.crypto.registry import load_backend_identity_registry
from klein.crypto.trust import load_trust_policy
from klein.verifier.signed_conformance import verify_signed_conformance


def verify_run_bundle(
    bundle_path: Path,
    *,
    backend_registry_path: Path | None = None,
    require_signed_registry: bool = False,
    require_backend_capabilities: bool = False,
) -> RunBundleResult:
    """Verify bundle integrity and signed-conformance for a directory or .kcprun bundle."""
    result = RunBundleResult(bundle_path=str(bundle_path))
    source = None
    try:
        source = load_bundle_source(bundle_path)
        result.bundle_format = source.bundle_format
        result.bundle_schema_status = "pass"
        result.bundle_hashes = dict(source.bundle.hashes)
        result.resolved_paths = _resolved_paths(source.root, source.bundle, bundle_path, source.bundle_format)
        _verify_entry_hashes(result, source.root, source.bundle)
        if result.bundle_entry_hash_status == "pass":
            _verify_artifact_entry(result, source.root / str(source.bundle.entries["artifact"]))
            signed = verify_signed_conformance(
                hail_path=source.root / str(source.bundle.entries["hail"]),
                manifest_path=source.root / str(source.bundle.entries["run_manifest"]),
                trust_policy_path=source.root / str(source.bundle.entries["trust_policy"]),
                artifact_path=source.root / str(source.bundle.entries["artifact"]),
                conformance_report_path=_optional_path(source.root, source.bundle.entries.get("conformance_report")),
                backend_registry_path=backend_registry_path
                or _optional_path(source.root, source.bundle.entries.get("backend_registry")),
                require_signed_registry=require_signed_registry,
            )
            result.signed_conformance_result = signed.to_dict()
            result.signed_conformance_status = signed.overall_status
            result.hail_digest = signed.hail_digest
            result.hail_chain_digest = signed.hail_chain_digest
            result.run_manifest_key_ids = signed.manifest_key_ids
            result.trust_status = signed.trust_status
            result.backend_id = signed.backend_id
            result.profile_id = signed.profile_id
            result.artifact_hash = signed.artifact_hash
            result.substrate_fingerprint = signed.substrate_fingerprint
            result.backend_registry_hash = signed.backend_registry_hash
            result.registry_signed = signed.registry_signed
            result.registry_signature_status = signed.registry_signature_status
            result.registry_provenance_status = signed.registry_provenance_status
            result.registry_authority_id = signed.registry_authority_id
            result.key_lifecycle_status = signed.key_lifecycle_status
            _verify_backend_capabilities(
                result,
                source.root,
                source.bundle,
                backend_registry_path
                or _optional_path(source.root, source.bundle.entries.get("backend_registry")),
                require_backend_capabilities=require_backend_capabilities,
            )
            if not signed.ok:
                error = signed.errors[0] if signed.errors else {}
                result.add_error(
                    "RUN_BUNDLE_SIGNED_CONFORMANCE_FAILED",
                    error.get("message", "signed-conformance verification failed"),
                    check="signed_conformance_status",
                )
        result.overall_status = (
            "pass"
            if result.bundle_schema_status == "pass"
            and result.bundle_entry_hash_status == "pass"
            and result.artifact_schema_status == "pass"
            and result.signed_conformance_status == "pass"
            and result.backend_capability_scope_status in {"pass", "not_evaluated", "not_applicable"}
            else "fail"
        )
        return result
    except RunBundleError as exc:
        check = _check_for_error(exc.error_code)
        if check == "bundle_schema_status":
            result.bundle_schema_status = "fail"
        else:
            result.bundle_entry_hash_status = "fail"
        result.add_error(exc.error_code, str(exc), check=check)
        result.overall_status = "fail"
        return result
    finally:
        if source is not None:
            source.close()


def inspect_run_bundle(bundle_path: Path) -> dict[str, Any]:
    """Return bundle manifest metadata without running signed-conformance verification."""
    source = load_bundle_source(bundle_path)
    try:
        return {
            "bundle_path": str(bundle_path),
            "bundle_format": source.bundle_format,
            "bundle": source.bundle.bundle,
            "resolved_paths": _resolved_paths(source.root, source.bundle, bundle_path, source.bundle_format),
        }
    finally:
        source.close()


def _verify_entry_hashes(result: RunBundleResult, root: Path, bundle: RunBundle) -> None:
    for key, entry in bundle.entries.items():
        expected = bundle.hashes.get(key)
        if entry is None:
            if expected is not None:
                result.bundle_entry_hash_status = "fail"
                result.add_error(
                    "RUN_BUNDLE_SCHEMA_INVALID",
                    f"hashes.{key} must be null when entries.{key} is null",
                    check="bundle_entry_hash_status",
                )
                return
            continue
        path = root / entry
        if not path.exists():
            result.bundle_entry_hash_status = "fail"
            result.add_error(
                "RUN_BUNDLE_MISSING_ENTRY",
                f"declared bundle entry missing: {entry}",
                check="bundle_entry_hash_status",
            )
            return
        actual = raw_file_sha256(path).ref
        if actual != expected:
            result.bundle_entry_hash_status = "fail"
            result.add_error(
                "RUN_BUNDLE_HASH_MISMATCH",
                f"{key} hash mismatch: expected {expected}, actual {actual}",
                check="bundle_entry_hash_status",
            )
            return
    result.bundle_entry_hash_status = "pass"


def _verify_artifact_entry(result: RunBundleResult, artifact_path: Path) -> None:
    try:
        validation = validate_artifact(artifact_path)
        digest = canonical_artifact_hash(artifact_path)
    except (OSError, ArtifactValidationError, ValueError, TypeError) as exc:
        result.artifact_schema_status = "fail"
        result.artifact_validation_error_code = getattr(exc, "error_code", "ARTIFACT_INVALID")
        result.add_error(result.artifact_validation_error_code, str(exc), check="artifact_schema_status")
        return
    result.artifact_type = validation.artifact_type
    result.artifact_schema_status = "pass" if validation.ok else "fail"
    result.artifact_canonicalization = digest.canonicalization
    if not validation.ok:
        result.artifact_validation_error_code = validation.error_code
        result.add_error(
            validation.error_code or "ARTIFACT_SCHEMA_INVALID",
            validation.message or "artifact validation failed",
            check="artifact_schema_status",
        )


def _verify_backend_capabilities(
    result: RunBundleResult,
    root: Path,
    bundle: RunBundle,
    backend_registry_path: Path | None,
    *,
    require_backend_capabilities: bool,
) -> None:
    capability_path = _optional_path(root, bundle.entries.get("backend_capabilities"))
    if capability_path is None:
        result.backend_capability_signature_status = "not_applicable" if not require_backend_capabilities else "missing"
        result.backend_capability_trust_status = "not_applicable" if not require_backend_capabilities else "untrusted"
        result.backend_capability_scope_status = "not_applicable" if not require_backend_capabilities else "fail"
        if require_backend_capabilities:
            result.backend_capability_error_code = "BACKEND_CAPABILITY_REQUIRED"
            result.add_error(
                "BACKEND_CAPABILITY_REQUIRED",
                "backend capability declaration is required",
                check="signed_conformance_status",
            )
        return
    result.backend_capabilities_present = True
    try:
        declaration = load_backend_capability_declaration(capability_path)
        level_result = verify_capability_declared_levels(declaration)
        registry = None if backend_registry_path is None else load_backend_identity_registry(backend_registry_path)
        trust_policy = load_trust_policy(root / str(bundle.entries["trust_policy"]))
        manifest = json.loads((root / str(bundle.entries["run_manifest"])).read_text(encoding="utf-8"))
        payload = manifest.get("payload", {}) if isinstance(manifest, dict) else {}
        verification = verify_backend_capability_declaration(
            declaration,
            registry=registry,
            trust_policy=trust_policy,
            backend_id=result.backend_id,
            backend_version=payload.get("backend_version") if isinstance(payload.get("backend_version"), str) else None,
            profile_id=result.profile_id,
            profile_version=payload.get("profile_version") if isinstance(payload.get("profile_version"), str) else None,
            mode=payload.get("mode") if isinstance(payload.get("mode"), str) else None,
            substrate_fingerprint=result.substrate_fingerprint,
            require_trust=True,
        )
    except (OSError, BackendCapabilityError) as exc:
        result.backend_capability_signature_status = "invalid"
        result.backend_capability_scope_status = "fail"
        result.backend_capability_error_code = getattr(exc, "error_code", "BACKEND_CAPABILITY_DECLARATION_INVALID")
        result.add_error(result.backend_capability_error_code, str(exc), check="signed_conformance_status")
        return
    result.backend_capability_declaration_hash = verification.declaration_hash
    result.backend_capability_signature_status = verification.signature_status
    result.backend_capability_trust_status = verification.trust_status
    result.backend_capability_scope_status = verification.capability_scope_status
    result.backend_capability_error_code = verification.error_code
    result.declared_conformance_levels = level_result.declared_levels
    result.verified_conformance_levels = level_result.verified_levels
    result.conformance_level_catalog_status = level_result.catalog_status
    result.conformance_level_dependency_status = level_result.dependency_status
    result.conformance_level_error_code = level_result.error_code
    if not verification.ok:
        result.add_error(
            verification.error_code or "BACKEND_CAPABILITY_DECLARATION_INVALID",
            verification.message or "backend capability verification failed",
            check="signed_conformance_status",
        )


def _resolved_paths(
    root: Path,
    bundle: RunBundle,
    bundle_path: Path,
    bundle_format: str,
) -> dict[str, str | None]:
    return {
        key: _resolved_entry(root, bundle_path, bundle_format, entry) if entry is not None else None
        for key, entry in bundle.entries.items()
    }


def _resolved_entry(root: Path, bundle_path: Path, bundle_format: str, entry: str) -> str:
    if bundle_format == "zip":
        return f"{bundle_path}!/{entry}"
    return str(root / entry)


def _optional_path(root: Path, entry: str | None) -> Path | None:
    return root / entry if entry is not None else None


def _check_for_error(error_code: str) -> str:
    if error_code in {"RUN_BUNDLE_SCHEMA_INVALID", "RUN_BUNDLE_INVALID", "RUN_BUNDLE_UNSUPPORTED_FORMAT"}:
        return "bundle_schema_status"
    return "bundle_entry_hash_status"


def result_json(result: RunBundleResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True)

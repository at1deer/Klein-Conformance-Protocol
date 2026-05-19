"""Reference verifier for KCP-Core-Signed-Conformance-v1."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from klein.common.hashing import hash_json_artifact, parse_ijson, raw_file_sha256
from klein.crypto.manifest import (
    RunManifestError,
    load_run_manifest,
    validate_manifest_payload_against_events,
    validate_run_manifest_structure,
    verify_run_manifest,
)
from klein.crypto.registry import BackendIdentityRegistryError, load_backend_identity_registry
from klein.crypto.trust import TrustPolicyError, load_trust_policy
from klein.hail.canonical import digest_hail_jsonl
from klein.hail.chain import verify_hail_chain
from klein.hail.validation import parse_jsonl_events, validate_events
from klein.verifier.result import SignedConformanceResult

SIGNED_CONFORMANCE_LEVEL = "KCP-Core-Signed-Conformance-v1"


def verify_signed_conformance(
    *,
    hail_path: Path | None = None,
    manifest_path: Path,
    trust_policy_path: Path | None,
    artifact_path: Path | None = None,
    conformance_report_path: Path | None = None,
    backend_registry_path: Path | None = None,
    require_signed_registry: bool = False,
    events: list[dict[str, Any]] | None = None,
) -> SignedConformanceResult:
    """Verify a run against KCP-Core-Signed-Conformance-v1."""
    result = SignedConformanceResult()

    parsed_events = _load_or_validate_events(result, hail_path=hail_path, events=events)
    if parsed_events is None:
        return _finish(result)

    _verify_hail_evidence(result, parsed_events)
    manifest = _load_manifest(result, manifest_path)
    trust_policy = _load_policy(result, trust_policy_path)
    backend_registry = _load_registry(result, backend_registry_path)

    if manifest is not None:
        _extract_manifest_fields(result, manifest)
        _verify_manifest_payload(result, manifest, parsed_events)
    if manifest is not None and trust_policy is not None:
        _verify_signature_and_trust(
            result,
            manifest,
            parsed_events,
            trust_policy,
            backend_registry,
            require_signed_registry=require_signed_registry,
        )

    _verify_artifact_binding(result, parsed_events, artifact_path)
    _verify_report_binding(result, conformance_report_path)
    return _finish(result)


def _load_or_validate_events(
    result: SignedConformanceResult,
    *,
    hail_path: Path | None,
    events: list[dict[str, Any]] | None,
) -> list[dict[str, Any]] | None:
    if events is not None:
        validation = validate_events(events)
        if not validation.ok:
            result.hail_schema_status = "fail"
            result.add_error(
                validation.error_code or "HAIL_SCHEMA_INVALID",
                validation.message,
                check="hail_schema_status",
            )
            return None
        result.hail_schema_status = "pass"
        return events
    if hail_path is None:
        result.hail_schema_status = "fail"
        result.add_error("HAIL_JSON_INVALID", "hail_path is required", check="hail_schema_status")
        return None
    validation, parsed = parse_jsonl_events(hail_path.read_text(encoding="utf-8"))
    if not validation.ok:
        result.hail_schema_status = "fail"
        result.add_error(
            validation.error_code or "HAIL_SCHEMA_INVALID",
            validation.message,
            check="hail_schema_status",
        )
        return None
    result.hail_schema_status = "pass"
    return parsed


def _verify_hail_evidence(result: SignedConformanceResult, events: list[dict[str, Any]]) -> None:
    try:
        result.hail_digest = f"sha256:{digest_hail_jsonl(events)}"
        result.canonicalization_status = "pass"
    except (TypeError, ValueError) as exc:
        result.canonicalization_status = "fail"
        result.add_error("HAIL_SCHEMA_INVALID", str(exc), check="canonicalization_status")

    run_starts = [event for event in events if event.get("kind") == "RUN_START"]
    run_ends = [event for event in events if event.get("kind") == "RUN_END"]
    if len(run_starts) != 1 or len(run_ends) != 1:
        result.lifecycle_status = "fail"
        result.add_error(
            "RUN_MANIFEST_LIFECYCLE_MISSING",
            "signed-conformance requires exactly one RUN_START and one RUN_END",
            check="lifecycle_status",
        )
    else:
        result.lifecycle_status = "pass"
        run_start = run_starts[0]
        result.backend_id = _string_or_none(run_start.get("backend_id"))
        result.profile_id = _string_or_none(run_start.get("profile_id"))
        result.profile_version = _string_or_none(run_start.get("profile_version"))
        result.artifact_hash = _string_or_none(run_start.get("artifact_hash"))
        result.substrate_fingerprint = _string_or_none(run_start.get("substrate_fingerprint"))

    chain = verify_hail_chain(events)
    if chain.ok and chain.result is not None:
        result.chain_status = "pass"
        result.hail_chain_digest = chain.result.terminal_chain_digest_ref
    else:
        result.chain_status = "fail"
        result.add_error(
            chain.error_code or "HAIL_CHAIN_INVALID",
            chain.reason or "HAIL chain verification failed",
            check="chain_status",
        )


def _load_manifest(result: SignedConformanceResult, manifest_path: Path) -> dict[str, Any] | None:
    try:
        manifest = load_run_manifest(manifest_path)
        validate_run_manifest_structure(manifest)
    except (OSError, RunManifestError) as exc:
        result.manifest_schema_status = "fail"
        result.add_error(
            getattr(exc, "error_code", "RUN_MANIFEST_INVALID"),
            str(exc),
            check="manifest_schema_status",
        )
        return None
    result.manifest_schema_status = "pass"
    return manifest


def _load_policy(result: SignedConformanceResult, trust_policy_path: Path | None) -> dict[str, Any] | None:
    if trust_policy_path is None:
        result.trust_status = "not_evaluated"
        result.add_error(
            "BACKEND_IDENTITY_UNTRUSTED",
            "signed-conformance requires a Trust Policy v1 document",
            check="trust_status",
        )
        return None
    try:
        policy = load_trust_policy(trust_policy_path)
    except (OSError, TrustPolicyError) as exc:
        result.trust_status = "fail"
        result.add_error(
            getattr(exc, "error_code", "TRUST_POLICY_INVALID"),
            str(exc),
            check="trust_status",
        )
        return None
    return policy


def _load_registry(result: SignedConformanceResult, backend_registry_path: Path | None) -> Any | None:
    if backend_registry_path is None:
        result.backend_identity_registry_status = "not_applicable"
        result.backend_identity_resolution_status = "not_applicable"
        return None
    try:
        registry = load_backend_identity_registry(backend_registry_path)
    except (OSError, BackendIdentityRegistryError) as exc:
        result.backend_identity_registry_status = "fail"
        result.backend_identity_resolution_status = "not_evaluated"
        result.add_error(
            getattr(exc, "error_code", "BACKEND_IDENTITY_REGISTRY_INVALID"),
            str(exc),
            check="backend_identity_registry_status",
        )
        return None
    result.backend_identity_registry_status = "pass"
    result.backend_registry_id = registry.registry_id
    result.backend_registry_hash = raw_file_sha256(backend_registry_path).ref
    return registry


def _extract_manifest_fields(result: SignedConformanceResult, manifest: dict[str, Any]) -> None:
    payload = manifest.get("payload", {})
    if isinstance(payload, dict):
        result.backend_id = _string_or_none(payload.get("backend_id")) or result.backend_id
        result.profile_id = _string_or_none(payload.get("profile_id")) or result.profile_id
        result.profile_version = _string_or_none(payload.get("profile_version")) or result.profile_version
        result.artifact_hash = _string_or_none(payload.get("artifact_hash")) or result.artifact_hash
        result.substrate_fingerprint = (
            _string_or_none(payload.get("substrate_fingerprint")) or result.substrate_fingerprint
        )
        result.hail_chain_digest = _string_or_none(payload.get("hail_chain_digest")) or result.hail_chain_digest
    signatures = manifest.get("signatures", [])
    if isinstance(signatures, list):
        result.manifest_key_ids = [
            signature["key_id"]
            for signature in signatures
            if isinstance(signature, dict) and isinstance(signature.get("key_id"), str)
        ]


def _verify_manifest_payload(
    result: SignedConformanceResult,
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    try:
        validate_manifest_payload_against_events(manifest["payload"], events)
    except (KeyError, RunManifestError) as exc:
        result.manifest_payload_status = "fail"
        result.add_error(
            getattr(exc, "error_code", "RUN_MANIFEST_PAYLOAD_MISMATCH"),
            str(exc),
            check="manifest_payload_status",
        )
        return
    result.manifest_payload_status = "pass"


def _verify_signature_and_trust(
    result: SignedConformanceResult,
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    trust_policy: dict[str, Any],
    backend_registry: Any | None,
    require_signed_registry: bool,
) -> None:
    verification = verify_run_manifest(
        manifest,
        events=events,
        trust_policy=trust_policy,
        backend_registry=backend_registry,
        require_registry_provenance=require_signed_registry,
    )
    result.signature_status = "pass" if verification.signature_status == "valid" else "fail"
    result.trust_status = "pass" if verification.trust_status == "trusted" else "fail"
    result.backend_identity_resolution_status = (
        "pass"
        if verification.identity_status == "resolved"
        else "not_applicable"
        if backend_registry is None
        else "fail"
    )
    result.identity_status = verification.identity_status
    result.backend_identity_status = verification.identity_status
    result.backend_registry_id = verification.backend_registry_id or result.backend_registry_id
    result.registry_backend_id = verification.registry_backend_id
    result.registry_key_id = verification.registry_key_id
    result.backend_key_status = verification.registry_key_status
    result.registry_signed = verification.registry_signed
    result.registry_signature_status = verification.registry_signature_status
    result.registry_provenance_status = verification.registry_provenance_status
    result.registry_authority_id = verification.registry_authority_id
    result.key_lifecycle_status = verification.key_lifecycle_status
    result.manifest_key_ids = list(verification.verified_key_ids)
    result.trusted_key_ids = list(verification.verified_key_ids) if verification.trust_status == "trusted" else []
    if not verification.ok:
        result.add_error(
            verification.error_code or "RUN_MANIFEST_INVALID",
            verification.message or verification.trust_reason,
            check="signature_status" if verification.signature_status != "valid" else "trust_status",
        )


def _verify_artifact_binding(
    result: SignedConformanceResult,
    events: list[dict[str, Any]],
    artifact_path: Path | None,
) -> None:
    run_start = next((event for event in events if event.get("kind") == "RUN_START"), None)
    if run_start is None:
        result.artifact_binding_status = "fail"
        return
    declared_hash = run_start.get("artifact_hash")
    if not isinstance(declared_hash, str) or not declared_hash:
        result.artifact_binding_status = "fail"
        result.add_error(
            "RUN_MANIFEST_PAYLOAD_MISMATCH",
            "RUN_START.artifact_hash missing",
            check="artifact_binding_status",
        )
        return
    result.artifact_hash = declared_hash
    if artifact_path is None:
        result.artifact_binding_status = "pass"
        result.add_warning(
            "artifact path not supplied; verifier checked declared lifecycle hash presence only",
            check="artifact_binding_status",
            code="artifact_not_supplied",
        )
        return
    try:
        actual = hash_json_artifact(artifact_path).ref
    except Exception as exc:  # noqa: BLE001 - normalize artifact hash failures.
        result.artifact_binding_status = "fail"
        result.add_error("ARTIFACT_JSON_INVALID", str(exc), check="artifact_binding_status")
        return
    if actual != declared_hash:
        result.artifact_binding_status = "fail"
        result.add_error(
            "RUN_MANIFEST_PAYLOAD_MISMATCH",
            f"artifact hash mismatch: expected {declared_hash}, actual {actual}",
            check="artifact_binding_status",
        )
        return
    result.artifact_binding_status = "pass"


def _verify_report_binding(
    result: SignedConformanceResult,
    conformance_report_path: Path | None,
) -> None:
    if conformance_report_path is None:
        result.report_binding_status = "not_applicable"
        return
    try:
        report = parse_ijson(conformance_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.report_binding_status = "fail"
        result.add_error("RUN_MANIFEST_INVALID", str(exc), check="report_binding_status")
        return
    if not isinstance(report, dict) or not isinstance(report.get("results"), list):
        result.report_binding_status = "fail"
        result.add_error(
            "RUN_MANIFEST_INVALID",
            "conformance report must contain results array",
            check="report_binding_status",
        )
        return
    try:
        from jsonschema import Draft7Validator

        schema_path = Path("schemas/conformance_report.schema.json")
        schema = parse_ijson(schema_path.read_text(encoding="utf-8"))
        Draft7Validator(schema).validate(report)
    except Exception as exc:  # noqa: BLE001 - normalize optional report validation failures.
        result.report_binding_status = "fail"
        result.add_error(
            "RUN_MANIFEST_INVALID",
            f"conformance report schema validation failed: {exc}",
            check="report_binding_status",
        )
        return
    if report["results"]:
        details = report["results"][0].get("details", {})
        if isinstance(details, dict):
            agreements = [
                ("run_start_artifact_hash", result.artifact_hash),
                ("run_start_backend_id", result.backend_id),
                ("run_start_profile_id", result.profile_id),
                ("run_start_profile_version", result.profile_version),
                ("run_start_substrate_fingerprint", result.substrate_fingerprint),
            ]
            mismatches = [
                field
                for field, expected in agreements
                if expected is not None and details.get(field) not in {None, expected}
            ]
            if mismatches:
                result.report_binding_status = "fail"
                result.add_error(
                    "RUN_MANIFEST_PAYLOAD_MISMATCH",
                    f"conformance report disagrees on field(s): {', '.join(mismatches)}",
                    check="report_binding_status",
                )
                return
    result.report_binding_status = "pass"


def _finish(result: SignedConformanceResult) -> SignedConformanceResult:
    required_statuses = [
        result.hail_schema_status,
        result.canonicalization_status,
        result.lifecycle_status,
        result.chain_status,
        result.manifest_schema_status,
        result.manifest_payload_status,
        result.signature_status,
        result.trust_status,
        result.artifact_binding_status,
    ]
    result.overall_status = "pass" if all(status == "pass" for status in required_statuses) else "fail"
    return result


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None

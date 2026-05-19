"""Run Manifest v1 construction and verification."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.common.hashing import canonical_json_sha256_ref, parse_ijson
from klein.crypto.keys import encode_base64_raw, raw_public_key
from klein.crypto.registry import BackendIdentityRegistry
from klein.crypto.signing import sign_payload, verify_payload_signature
from klein.crypto.trust import TrustPolicyError, evaluate_trust_policy
from klein.hail.canonical import digest_hail_jsonl, hash_hail_jsonl
from klein.hail.chain import HAIL_CHAIN_ALGORITHM, verify_hail_chain
from klein.hail.validation import parse_jsonl_events, validate_events

RUN_MANIFEST_VERSION = "klein.run_manifest.v1"
RUN_MANIFEST_CANONICALIZATION = "klein.canon.json.v1"
HAIL_CANONICALIZATION = "klein.canon.jsonl.v1"
_SHA256_REF_RE = re.compile(r"^sha256:[a-f0-9]{64}$")


class RunManifestError(ValueError):
    """Structured Run Manifest v1 failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class RunManifestVerification:
    """Verification result for a signed run manifest."""

    ok: bool
    signature_count: int = 0
    verified_key_ids: tuple[str, ...] = ()
    signature_status: str = "missing"
    trust_status: str = "not_evaluated"
    trust_reason: str = "no_trust_policy"
    error_code: str | None = None
    message: str | None = None
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


def load_hail_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Parse and validate a strict HAIL v1 JSONL stream from disk."""
    validation, events = parse_jsonl_events(Path(path).read_text(encoding="utf-8"))
    if not validation.ok:
        raise RunManifestError(
            "RUN_MANIFEST_INVALID",
            f"HAIL validation failed: {validation.error_code} {validation.message}",
        )
    return events


def load_run_manifest(path: str | Path) -> dict[str, Any]:
    """Load a Run Manifest JSON object with duplicate-key and non-finite rejection."""
    try:
        manifest = parse_ijson(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RunManifestError("RUN_MANIFEST_INVALID", f"manifest JSON parse failed: {exc}") from exc
    if not isinstance(manifest, dict):
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "manifest must be a JSON object")
    return manifest


def _require_sha256_ref(value: Any, field: str) -> None:
    if not isinstance(value, str) or not _SHA256_REF_RE.match(value):
        raise RunManifestError(
            "RUN_MANIFEST_SCHEMA_INVALID",
            f"payload.{field} must be a sha256:<hex> reference",
        )


def validate_run_manifest_structure(manifest: dict[str, Any]) -> None:
    """Validate the minimal Run Manifest v1 structure used by tools."""
    if manifest.get("manifest_version") != RUN_MANIFEST_VERSION:
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "invalid manifest_version")
    payload = manifest.get("payload")
    if not isinstance(payload, dict):
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "payload must be an object")
    signatures = manifest.get("signatures")
    if not isinstance(signatures, list):
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "signatures must be an array")

    required_payload_fields = {
        "run_id",
        "created_by",
        "created_at",
        "hail_canonicalization",
        "hail_digest",
        "hail_chain_algorithm",
        "hail_chain_digest",
        "preclose_hail_digest",
        "preclose_hail_chain_digest",
        "event_count",
        "event_count_preclose",
        "artifact_type",
        "artifact_hash",
        "artifact_canonicalization",
        "profile_id",
        "profile_version",
        "backend_id",
        "backend_version",
        "mode",
        "substrate_capabilities_hash",
        "substrate_topology_hash",
        "substrate_fingerprint",
        "run_status",
        "error_code",
        "conformance_summary_hash",
    }
    missing = sorted(required_payload_fields - set(payload))
    if missing:
        raise RunManifestError(
            "RUN_MANIFEST_SCHEMA_INVALID",
            f"payload missing required field(s): {', '.join(missing)}",
        )
    for field in (
        "hail_digest",
        "hail_chain_digest",
        "preclose_hail_digest",
        "preclose_hail_chain_digest",
        "artifact_hash",
    ):
        _require_sha256_ref(payload.get(field), field)
    for nullable_hash in (
        "substrate_capabilities_hash",
        "substrate_topology_hash",
        "substrate_fingerprint",
        "conformance_summary_hash",
    ):
        value = payload.get(nullable_hash)
        if value is not None:
            _require_sha256_ref(value, nullable_hash)
    if payload.get("hail_canonicalization") != HAIL_CANONICALIZATION:
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "invalid hail_canonicalization")
    if payload.get("hail_chain_algorithm") != HAIL_CHAIN_ALGORITHM:
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "invalid hail_chain_algorithm")
    if payload.get("mode") not in {"HARD", "ENVELOPE", "DIAGNOSTIC"}:
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "invalid mode")
    if payload.get("run_status") not in {"SUCCESS", "FAIL", "ERROR"}:
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "invalid run_status")
    if not isinstance(payload.get("event_count"), int) or payload["event_count"] < 0:
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "invalid event_count")
    if not isinstance(payload.get("event_count_preclose"), int) or payload["event_count_preclose"] < 0:
        raise RunManifestError("RUN_MANIFEST_SCHEMA_INVALID", "invalid event_count_preclose")


def _lifecycle_events(events: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    run_starts = [event for event in events if event.get("kind") == "RUN_START"]
    run_ends = [event for event in events if event.get("kind") == "RUN_END"]
    if len(run_starts) != 1 or len(run_ends) != 1:
        raise RunManifestError(
            "RUN_MANIFEST_LIFECYCLE_MISSING",
            "Run Manifest v1 requires exactly one RUN_START and one RUN_END event",
        )
    if run_starts[0].get("run_id") != run_ends[0].get("run_id"):
        raise RunManifestError("RUN_MANIFEST_LIFECYCLE_MISSING", "RUN_START/RUN_END run_id mismatch")
    return run_starts[0], run_ends[0]


def _conformance_summary_hash(summary: Any | None) -> str | None:
    if summary is None:
        return None
    if isinstance(summary, Path):
        summary = parse_ijson(summary.read_text(encoding="utf-8"))
    return canonical_json_sha256_ref(summary)


def build_run_manifest_payload(
    events: list[dict[str, Any]],
    *,
    conformance_summary: Any | None = None,
    created_at: str | None = None,
    created_by: str = "klein-protocol",
) -> dict[str, Any]:
    """Construct a Run Manifest v1 payload from lifecycle-bound HAIL events."""
    validation = validate_events(events)
    if not validation.ok:
        raise RunManifestError(
            "RUN_MANIFEST_INVALID",
            f"HAIL validation failed: {validation.error_code} {validation.message}",
        )
    run_start, run_end = _lifecycle_events(events)

    chain = verify_hail_chain(events)
    if not chain.ok or chain.result is None:
        code = (
            "RUN_MANIFEST_LIFECYCLE_MISSING"
            if chain.error_code == "HAIL_RUN_END_MISSING"
            else "RUN_MANIFEST_CHAIN_INVALID"
        )
        raise RunManifestError(code, chain.reason or "HAIL chain verification failed")

    preclose_events = [event for event in events if event.get("kind") != "RUN_END"]
    preclose_hash = hash_hail_jsonl(preclose_events).ref
    if preclose_hash != run_end.get("preclose_hail_digest"):
        raise RunManifestError(
            "RUN_MANIFEST_PAYLOAD_MISMATCH",
            "RUN_END.preclose_hail_digest does not match computed preclose HAIL digest",
        )
    if chain.result.event_count_chained != run_end.get("event_count_preclose"):
        raise RunManifestError(
            "RUN_MANIFEST_PAYLOAD_MISMATCH",
            "RUN_END.event_count_preclose does not match the chained event count",
        )
    artifact_hash = run_start.get("artifact_hash")
    if not isinstance(artifact_hash, str) or not artifact_hash:
        raise RunManifestError("RUN_MANIFEST_PAYLOAD_MISMATCH", "RUN_START.artifact_hash missing")

    return {
        "run_id": run_start["run_id"],
        "created_by": created_by,
        "created_at": created_at,
        "hail_canonicalization": HAIL_CANONICALIZATION,
        "hail_digest": f"sha256:{digest_hail_jsonl(events)}",
        "hail_chain_algorithm": HAIL_CHAIN_ALGORITHM,
        "hail_chain_digest": chain.result.terminal_chain_digest_ref,
        "preclose_hail_digest": run_end["preclose_hail_digest"],
        "preclose_hail_chain_digest": run_end["preclose_hail_chain_digest"],
        "event_count": len(events),
        "event_count_preclose": run_end["event_count_preclose"],
        "artifact_type": run_start["artifact_type"],
        "artifact_hash": artifact_hash,
        "artifact_canonicalization": run_start["artifact_canonicalization"],
        "profile_id": run_start["profile_id"],
        "profile_version": run_start["profile_version"],
        "backend_id": run_start["backend_id"],
        "backend_version": run_start["backend_version"],
        "mode": run_start["mode"],
        "substrate_capabilities_hash": run_start.get("substrate_capabilities_hash"),
        "substrate_topology_hash": run_start.get("substrate_topology_hash"),
        "substrate_fingerprint": run_start.get("substrate_fingerprint"),
        "run_status": run_end["status"],
        "error_code": run_end.get("error_code"),
        "conformance_summary_hash": _conformance_summary_hash(conformance_summary),
    }


def sign_run_manifest(
    payload: dict[str, Any],
    private_key: Any,
    *,
    key_id: str,
) -> dict[str, Any]:
    """Create a signed Run Manifest v1 object for a payload."""
    manifest = {
        "manifest_version": RUN_MANIFEST_VERSION,
        "payload": payload,
        "signatures": [sign_payload(payload, private_key, key_id=key_id)],
    }
    validate_run_manifest_structure(manifest)
    return manifest


def unsigned_run_manifest(payload: dict[str, Any]) -> dict[str, Any]:
    """Create an unsigned Run Manifest v1 object for fixture/debug use."""
    manifest = {
        "manifest_version": RUN_MANIFEST_VERSION,
        "payload": payload,
        "signatures": [],
    }
    validate_run_manifest_structure(manifest)
    return manifest


def validate_manifest_payload_against_events(
    payload: dict[str, Any],
    events: list[dict[str, Any]],
) -> None:
    """Ensure a manifest payload externally binds the supplied HAIL stream."""
    expected = build_run_manifest_payload(
        events,
        conformance_summary=None,
        created_at=payload.get("created_at"),
        created_by=str(payload.get("created_by", "klein-protocol")),
    )
    comparable_fields = set(expected) - {"conformance_summary_hash"}
    mismatches = [
        field
        for field in sorted(comparable_fields)
        if payload.get(field) != expected.get(field)
    ]
    if mismatches:
        raise RunManifestError(
            "RUN_MANIFEST_PAYLOAD_MISMATCH",
            f"manifest payload does not match HAIL field(s): {', '.join(mismatches)}",
        )


def _trust_status(
    signatures: list[dict[str, Any]],
    *,
    trusted_key_id: str | None,
    trusted_public_key: Any | None,
) -> str:
    if trusted_key_id is None and trusted_public_key is None:
        return "not_evaluated"
    trusted_public_key_b64 = (
        encode_base64_raw(raw_public_key(trusted_public_key))
        if trusted_public_key is not None
        else None
    )
    for signature in signatures:
        if trusted_key_id is not None and signature.get("key_id") != trusted_key_id:
            continue
        if trusted_public_key_b64 is not None and signature.get("public_key") != trusted_public_key_b64:
            continue
        return "trusted"
    return "untrusted"


def verify_run_manifest(
    manifest: dict[str, Any],
    *,
    events: list[dict[str, Any]] | None = None,
    trusted_key_id: str | None = None,
    trusted_public_key: Any | None = None,
    trust_policy: dict[str, Any] | None = None,
    backend_registry: BackendIdentityRegistry | dict[str, Any] | None = None,
    require_registry_provenance: bool = False,
) -> RunManifestVerification:
    """Verify Run Manifest v1 schema, payload binding, signatures, and optional trust."""
    try:
        validate_run_manifest_structure(manifest)
        payload = manifest["payload"]
        signatures = manifest["signatures"]
        if not signatures:
            raise RunManifestError(
                "RUN_MANIFEST_SIGNATURE_MISSING",
                "manifest has no signatures",
            )
        if events is not None:
            validate_manifest_payload_against_events(payload, events)
    except RunManifestError as exc:
        signature_status = "missing" if exc.error_code == "RUN_MANIFEST_SIGNATURE_MISSING" else "invalid"
        return RunManifestVerification(
            ok=False,
            signature_status=signature_status,
            error_code=exc.error_code,
            message=str(exc),
        )

    verified_key_ids: list[str] = []
    verified_signatures: list[dict[str, Any]] = []
    for signature in signatures:
        if not isinstance(signature, dict):
            return RunManifestVerification(
                ok=False,
                signature_count=len(signatures),
                signature_status="invalid",
                error_code="RUN_MANIFEST_SIGNATURE_INVALID",
                message="signature entries must be objects",
            )
        verification = verify_payload_signature(payload, signature)
        if not verification.ok:
            return RunManifestVerification(
                ok=False,
                signature_count=len(signatures),
                verified_key_ids=tuple(verified_key_ids),
                signature_status="invalid",
                error_code=verification.error_code,
                message=verification.message,
            )
        if verification.key_id is not None:
            verified_key_ids.append(verification.key_id)
        verified_signatures.append(signature)

    trust = _trust_status(
        signatures,
        trusted_key_id=trusted_key_id,
        trusted_public_key=trusted_public_key,
    )
    trust_reason = "no_trust_policy"
    trust_error_code = "BACKEND_IDENTITY_UNTRUSTED" if trust == "untrusted" else None
    identity_status = "not_evaluated"
    backend_registry_id = None
    registry_backend_id = None
    registry_key_id = None
    registry_key_status = None
    registry_signed = False
    registry_signature_status = "not_applicable"
    registry_provenance_status = "not_evaluated"
    registry_authority_id = None
    key_lifecycle_status = None
    if trusted_key_id is not None or trusted_public_key is not None:
        trust_reason = "trusted_key_match" if trust == "trusted" else "trusted_key_mismatch"

    if trust_policy is not None:
        try:
            policy_results = [
                evaluate_trust_policy(trust_policy, manifest=manifest, signature=signature)
                if backend_registry is None
                else evaluate_trust_policy(
                    trust_policy,
                    manifest=manifest,
                    signature=signature,
                    backend_registry=backend_registry,
                    require_registry_provenance=require_registry_provenance,
                )
                for signature in verified_signatures
            ]
        except TrustPolicyError as exc:
            return RunManifestVerification(
                ok=False,
                signature_count=len(signatures),
                verified_key_ids=tuple(verified_key_ids),
                signature_status="valid",
                trust_status="indeterminate",
                trust_reason="trust_policy_invalid",
                error_code=exc.error_code,
                message=str(exc),
            )
        trusted_results = [result for result in policy_results if result.trusted]
        if trusted_results:
            selected = trusted_results[0]
            trust = "trusted"
            trust_reason = selected.trust_reason
            trust_error_code = None
            identity_status = selected.identity_status
            backend_registry_id = selected.backend_registry_id
            registry_backend_id = selected.registry_backend_id
            registry_key_id = selected.registry_key_id
            registry_key_status = selected.registry_key_status
            registry_signed = selected.registry_signed
            registry_signature_status = selected.registry_signature_status
            registry_provenance_status = selected.registry_provenance_status
            registry_authority_id = selected.registry_authority_id
            key_lifecycle_status = selected.key_lifecycle_status
        else:
            selected = policy_results[0]
            trust = selected.trust_status
            trust_reason = selected.trust_reason
            trust_error_code = selected.error_code
            identity_status = selected.identity_status
            backend_registry_id = selected.backend_registry_id
            registry_backend_id = selected.registry_backend_id
            registry_key_id = selected.registry_key_id
            registry_key_status = selected.registry_key_status
            registry_signed = selected.registry_signed
            registry_signature_status = selected.registry_signature_status
            registry_provenance_status = selected.registry_provenance_status
            registry_authority_id = selected.registry_authority_id
            key_lifecycle_status = selected.key_lifecycle_status
    if trust in {"untrusted", "indeterminate"}:
        return RunManifestVerification(
            ok=False,
            signature_count=len(signatures),
            verified_key_ids=tuple(verified_key_ids),
            signature_status="valid",
            trust_status=trust,
            trust_reason=trust_reason,
            error_code=trust_error_code or "BACKEND_IDENTITY_UNTRUSTED",
            message=f"signature is valid but trust policy did not authorize it: {trust_reason}",
            identity_status=identity_status,
            backend_registry_id=backend_registry_id,
            registry_backend_id=registry_backend_id,
            registry_key_id=registry_key_id,
            registry_key_status=registry_key_status,
            registry_signed=registry_signed,
            registry_signature_status=registry_signature_status,
            registry_provenance_status=registry_provenance_status,
            registry_authority_id=registry_authority_id,
            key_lifecycle_status=key_lifecycle_status,
        )
    return RunManifestVerification(
        ok=True,
        signature_count=len(signatures),
        verified_key_ids=tuple(verified_key_ids),
        signature_status="valid",
        trust_status=trust,
        trust_reason=trust_reason,
        identity_status=identity_status,
        backend_registry_id=backend_registry_id,
        registry_backend_id=registry_backend_id,
        registry_key_id=registry_key_id,
        registry_key_status=registry_key_status,
        registry_signed=registry_signed,
        registry_signature_status=registry_signature_status,
        registry_provenance_status=registry_provenance_status,
        registry_authority_id=registry_authority_id,
        key_lifecycle_status=key_lifecycle_status,
    )

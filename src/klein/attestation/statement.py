"""Attestation statement validation, hashing, and inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.attestation.validation import (
    AttestationValidationResult,
    failure,
    is_sha256_ref,
    require_fields,
    require_object,
)
from klein.common.hashing import HashResult, hash_json_artifact, hash_json_value, parse_ijson

ATTESTATION_STATEMENT_VERSION = "klein.attestation_statement.v1"
SUPPORTED_STATEMENT_KINDS = {"none", "mock"}
KNOWN_SUBJECT_TYPES = {"backend", "run_bundle", "recorded_run", "device"}
ATTESTATION_STATUSES = {"not_present", "not_evaluated", "none", "mock", "invalid", "attested_future"}
STATEMENT_REQUIRED_FIELDS = (
    "attestation_statement_version",
    "statement_id",
    "statement_kind",
    "subject",
    "backend",
    "hardware_attestation_claimed",
    "hardware_root",
    "quote",
    "measurements",
    "signature",
    "metadata",
)


@dataclass(frozen=True)
class AttestationInspection:
    attestation_status: str
    hardware_attestation_claimed: bool
    statement_kind: str | None
    subject_type: str | None
    subject_id: str | None
    subject_hash: str | None
    backend_id: str | None
    message: str


def load_attestation_statement(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("attestation statement root must be an object")
    return data


def canonical_attestation_statement_hash(data_or_path: dict[str, Any] | str | Path) -> HashResult:
    if isinstance(data_or_path, str | Path):
        return hash_json_artifact(Path(data_or_path))
    return hash_json_value(data_or_path)


def validate_attestation_statement(
    data: dict[str, Any],
    strict_current_alpha: bool = True,
) -> AttestationValidationResult:
    if result := require_object(data, "ATTESTATION_STATEMENT_SCHEMA_INVALID", "attestation statement"):
        return result
    if result := require_fields(data, STATEMENT_REQUIRED_FIELDS, "ATTESTATION_STATEMENT_SCHEMA_INVALID"):
        return result
    if data.get("attestation_statement_version") != ATTESTATION_STATEMENT_VERSION:
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "unsupported attestation_statement_version")
    if not isinstance(data.get("statement_id"), str) or not data["statement_id"]:
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "statement_id must be a non-empty string")

    subject = data.get("subject")
    if not isinstance(subject, dict):
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "subject must be an object")
    if result := require_fields(subject, ("subject_type", "subject_id", "subject_hash"), "ATTESTATION_STATEMENT_SCHEMA_INVALID"):
        return result
    if subject.get("subject_type") not in KNOWN_SUBJECT_TYPES:
        return failure("ATTESTATION_STATEMENT_INVALID", "subject_type must be a known attestation subject")
    subject_id = subject.get("subject_id")
    if subject_id is not None and (not isinstance(subject_id, str) or not subject_id):
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "subject_id must be null or a non-empty string")
    subject_hash = subject.get("subject_hash")
    if subject_hash is not None and not is_sha256_ref(subject_hash):
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "subject_hash must be sha256:<64 lowercase hex>")

    backend = data.get("backend")
    if not isinstance(backend, dict):
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "backend must be an object")
    if result := require_fields(backend, ("backend_id", "backend_version"), "ATTESTATION_STATEMENT_SCHEMA_INVALID"):
        return result
    backend_id = backend.get("backend_id")
    backend_version = backend.get("backend_version")
    if backend_id is not None and (not isinstance(backend_id, str) or not backend_id):
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "backend_id must be null or a non-empty string")
    if backend_version is not None and (not isinstance(backend_version, str) or not backend_version):
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "backend_version must be null or a non-empty string")
    if not isinstance(data.get("measurements"), list):
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "measurements must be a list")
    if not isinstance(data.get("metadata"), dict):
        return failure("ATTESTATION_STATEMENT_SCHEMA_INVALID", "metadata must be an object")

    if strict_current_alpha:
        if data.get("statement_kind") not in SUPPORTED_STATEMENT_KINDS:
            return failure("ATTESTATION_STATEMENT_INVALID", "CURRENT_ALPHA supports statement_kind none/mock only")
        if data.get("hardware_attestation_claimed") is not False:
            return failure(
                "ATTESTATION_HARDWARE_UNSUPPORTED",
                "CURRENT_ALPHA attestation statements must not claim hardware attestation",
            )
        if data.get("hardware_root") is not None:
            return failure("ATTESTATION_HARDWARE_ROOT_UNSUPPORTED", "CURRENT_ALPHA does not support hardware roots")
        if data.get("quote") is not None:
            return failure("ATTESTATION_QUOTE_UNSUPPORTED", "CURRENT_ALPHA does not support attestation quotes")
        if data.get("signature") is not None:
            return failure("ATTESTATION_SIGNATURE_UNSUPPORTED", "none/mock statements must not include signatures")
        if data.get("measurements") != []:
            return failure("ATTESTATION_STATEMENT_INVALID", "CURRENT_ALPHA none/mock statements use no measurements")
    return AttestationValidationResult(ok=True)


def verify_attestation_statement_binding(
    statement: dict[str, Any],
    subject_hash: str | None = None,
    backend_id: str | None = None,
) -> AttestationValidationResult:
    validation = validate_attestation_statement(statement)
    if not validation.ok:
        return validation
    if subject_hash is not None:
        if not is_sha256_ref(subject_hash):
            return failure("ATTESTATION_SUBJECT_HASH_MISMATCH", "subject_hash argument must be sha256:<64 lowercase hex>")
        statement_subject_hash = statement["subject"].get("subject_hash")
        if statement_subject_hash != subject_hash:
            return failure(
                "ATTESTATION_SUBJECT_HASH_MISMATCH",
                f"attestation statement targets {statement_subject_hash}, not {subject_hash}",
            )
    if backend_id is not None and statement["backend"].get("backend_id") != backend_id:
        return failure(
            "ATTESTATION_BACKEND_MISMATCH",
            f"attestation statement backend is {statement['backend'].get('backend_id')}, not {backend_id}",
        )
    return AttestationValidationResult(ok=True)


def inspect_attestation_statement(data: dict[str, Any] | None) -> AttestationInspection:
    if data is None:
        return AttestationInspection("not_present", False, None, None, None, None, None, "no attestation statement present")
    validation = validate_attestation_statement(data)
    if not validation.ok:
        subject = data.get("subject") if isinstance(data, dict) else {}
        backend = data.get("backend") if isinstance(data, dict) else {}
        return AttestationInspection(
            "invalid",
            bool(data.get("hardware_attestation_claimed")) if isinstance(data, dict) else False,
            data.get("statement_kind") if isinstance(data, dict) else None,
            subject.get("subject_type") if isinstance(subject, dict) else None,
            subject.get("subject_id") if isinstance(subject, dict) else None,
            subject.get("subject_hash") if isinstance(subject, dict) else None,
            backend.get("backend_id") if isinstance(backend, dict) else None,
            validation.message or "attestation statement invalid",
        )
    status = data["statement_kind"]
    return AttestationInspection(
        status,
        False,
        data["statement_kind"],
        data["subject"]["subject_type"],
        data["subject"].get("subject_id"),
        data["subject"].get("subject_hash"),
        data["backend"].get("backend_id"),
        f"valid {status} attestation statement; no hardware attestation proof is claimed",
    )

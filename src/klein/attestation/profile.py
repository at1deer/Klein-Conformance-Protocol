"""Attestation profile validation and hashing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from klein.attestation.validation import (
    AttestationValidationResult,
    failure,
    require_fields,
    require_object,
)
from klein.common.hashing import HashResult, hash_json_artifact, hash_json_value, parse_ijson

ATTESTATION_PROFILE_VERSION = "klein.attestation_profile.v1"
SUPPORTED_PROFILE_KIND = "mock_none"
SUPPORTED_STATEMENT_KINDS = {"none", "mock"}
PROFILE_REQUIRED_FIELDS = (
    "attestation_profile_version",
    "profile_id",
    "profile_kind",
    "hardware_attestation_claimed",
    "allowed_statement_kinds",
    "requires_hardware_root",
    "trust_roots",
    "limitations",
)


def load_attestation_profile(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("attestation profile root must be an object")
    return data


def canonical_attestation_profile_hash(data_or_path: dict[str, Any] | str | Path) -> HashResult:
    if isinstance(data_or_path, str | Path):
        return hash_json_artifact(Path(data_or_path))
    return hash_json_value(data_or_path)


def validate_attestation_profile(
    data: dict[str, Any],
    strict_current_alpha: bool = True,
) -> AttestationValidationResult:
    if result := require_object(data, "ATTESTATION_PROFILE_SCHEMA_INVALID", "attestation profile"):
        return result
    if result := require_fields(data, PROFILE_REQUIRED_FIELDS, "ATTESTATION_PROFILE_SCHEMA_INVALID"):
        return result
    if data.get("attestation_profile_version") != ATTESTATION_PROFILE_VERSION:
        return failure("ATTESTATION_PROFILE_SCHEMA_INVALID", "unsupported attestation_profile_version")
    if not isinstance(data.get("profile_id"), str) or not data["profile_id"]:
        return failure("ATTESTATION_PROFILE_SCHEMA_INVALID", "profile_id must be a non-empty string")
    allowed_statement_kinds = data.get("allowed_statement_kinds")
    if not isinstance(allowed_statement_kinds, list) or not allowed_statement_kinds:
        return failure("ATTESTATION_PROFILE_SCHEMA_INVALID", "allowed_statement_kinds must be non-empty")
    if not all(isinstance(kind, str) for kind in allowed_statement_kinds):
        return failure("ATTESTATION_PROFILE_SCHEMA_INVALID", "allowed_statement_kinds must be strings")
    limitations = data.get("limitations")
    if not isinstance(limitations, list) or not all(isinstance(item, str) and item for item in limitations):
        return failure("ATTESTATION_PROFILE_SCHEMA_INVALID", "limitations must be non-empty strings")
    if not isinstance(data.get("trust_roots"), list):
        return failure("ATTESTATION_PROFILE_SCHEMA_INVALID", "trust_roots must be a list")

    if strict_current_alpha:
        if data.get("profile_kind") != SUPPORTED_PROFILE_KIND:
            return failure("ATTESTATION_PROFILE_INVALID", "CURRENT_ALPHA supports profile_kind mock_none only")
        if data.get("hardware_attestation_claimed") is not False:
            return failure(
                "ATTESTATION_HARDWARE_UNSUPPORTED",
                "CURRENT_ALPHA attestation profiles must not claim hardware attestation",
            )
        if data.get("requires_hardware_root") is not False:
            return failure(
                "ATTESTATION_HARDWARE_ROOT_UNSUPPORTED",
                "CURRENT_ALPHA attestation profiles must not require a hardware root",
            )
        if not set(allowed_statement_kinds).issubset(SUPPORTED_STATEMENT_KINDS):
            return failure("ATTESTATION_PROFILE_INVALID", "CURRENT_ALPHA allows none/mock statements only")
        if data.get("trust_roots") != []:
            return failure("ATTESTATION_PROFILE_INVALID", "CURRENT_ALPHA attestation profiles use no trust roots")
    return AttestationValidationResult(ok=True)

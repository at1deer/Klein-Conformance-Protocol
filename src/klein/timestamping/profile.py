"""Timestamp profile validation and hashing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from klein.common.hashing import HashResult, hash_json_artifact, hash_json_value, parse_ijson
from klein.timestamping.validation import (
    TimestampValidationResult,
    failure,
    require_fields,
    require_object,
)

TIMESTAMP_PROFILE_VERSION = "klein.timestamp_profile.v1"
SUPPORTED_PROFILE_KIND = "mock_local"
SUPPORTED_TOKEN_KIND = "mock_local"
PROFILE_REQUIRED_FIELDS = (
    "timestamp_profile_version",
    "profile_id",
    "profile_kind",
    "trusted_time_claimed",
    "allowed_token_kinds",
    "requires_external_time_authority",
    "trust_roots",
    "limitations",
)


def load_timestamp_profile(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("timestamp profile root must be an object")
    return data


def canonical_timestamp_profile_hash(data_or_path: dict[str, Any] | str | Path) -> HashResult:
    if isinstance(data_or_path, str | Path):
        return hash_json_artifact(Path(data_or_path))
    return hash_json_value(data_or_path)


def validate_timestamp_profile(
    data: dict[str, Any],
    strict_current_alpha: bool = True,
) -> TimestampValidationResult:
    if result := require_object(data, "TIMESTAMP_PROFILE_SCHEMA_INVALID", "timestamp profile"):
        return result
    if result := require_fields(data, PROFILE_REQUIRED_FIELDS, "TIMESTAMP_PROFILE_SCHEMA_INVALID"):
        return result
    if data.get("timestamp_profile_version") != TIMESTAMP_PROFILE_VERSION:
        return failure("TIMESTAMP_PROFILE_SCHEMA_INVALID", "unsupported timestamp_profile_version")
    if not isinstance(data.get("profile_id"), str) or not data["profile_id"]:
        return failure("TIMESTAMP_PROFILE_SCHEMA_INVALID", "profile_id must be a non-empty string")
    allowed_token_kinds = data.get("allowed_token_kinds")
    if not isinstance(allowed_token_kinds, list) or not allowed_token_kinds:
        return failure("TIMESTAMP_PROFILE_SCHEMA_INVALID", "allowed_token_kinds must be non-empty")
    if not all(isinstance(kind, str) for kind in allowed_token_kinds):
        return failure("TIMESTAMP_PROFILE_SCHEMA_INVALID", "allowed_token_kinds must be strings")
    limitations = data.get("limitations")
    if not isinstance(limitations, list) or not all(isinstance(item, str) and item for item in limitations):
        return failure("TIMESTAMP_PROFILE_SCHEMA_INVALID", "limitations must be non-empty strings")
    if not isinstance(data.get("trust_roots"), list):
        return failure("TIMESTAMP_PROFILE_SCHEMA_INVALID", "trust_roots must be a list")

    if strict_current_alpha:
        if data.get("profile_kind") != SUPPORTED_PROFILE_KIND:
            return failure("TIMESTAMP_PROFILE_INVALID", "CURRENT_ALPHA supports profile_kind mock_local only")
        if data.get("trusted_time_claimed") is not False:
            return failure(
                "TIMESTAMP_TRUSTED_TIME_UNSUPPORTED",
                "CURRENT_ALPHA timestamp profiles must not claim trusted time",
            )
        if data.get("requires_external_time_authority") is not False:
            return failure(
                "TIMESTAMP_TSA_UNSUPPORTED",
                "CURRENT_ALPHA timestamp profiles must not require an external time authority",
            )
        if set(allowed_token_kinds) != {SUPPORTED_TOKEN_KIND}:
            return failure("TIMESTAMP_PROFILE_INVALID", "CURRENT_ALPHA allows mock_local tokens only")
        if data.get("trust_roots") != []:
            return failure("TIMESTAMP_PROFILE_INVALID", "CURRENT_ALPHA timestamp profiles use no trust roots")
    return TimestampValidationResult(ok=True)

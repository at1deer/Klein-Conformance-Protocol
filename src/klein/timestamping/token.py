"""Timestamp token validation, hashing, and inspection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.common.hashing import HashResult, hash_json_artifact, hash_json_value, parse_ijson
from klein.timestamping.validation import (
    TimestampValidationResult,
    failure,
    is_sha256_ref,
    require_fields,
    require_object,
    validate_utc_z_timestamp,
)

TIMESTAMP_TOKEN_VERSION = "klein.timestamp_token.v1"
SUPPORTED_TOKEN_KIND = "mock_local"
KNOWN_TARGET_TYPES = {"run_bundle", "run_manifest", "hail_chain", "recorded_run"}
CURRENT_ALPHA_SOURCES = {"local_clock", "mock"}
TIMESTAMP_STATUSES = {"not_present", "not_evaluated", "mock", "invalid", "trusted_future"}
TOKEN_REQUIRED_FIELDS = (
    "timestamp_token_version",
    "token_id",
    "token_kind",
    "target",
    "claimed_time",
    "time_source",
    "trusted_time_claimed",
    "signature",
    "metadata",
)


@dataclass(frozen=True)
class TimestampInspection:
    timestamp_status: str
    trusted_time_claimed: bool
    token_kind: str | None
    target_type: str | None
    target_hash: str | None
    message: str


def load_timestamp_token(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("timestamp token root must be an object")
    return data


def canonical_timestamp_token_hash(data_or_path: dict[str, Any] | str | Path) -> HashResult:
    if isinstance(data_or_path, str | Path):
        return hash_json_artifact(Path(data_or_path))
    return hash_json_value(data_or_path)


def validate_timestamp_token(
    data: dict[str, Any],
    strict_current_alpha: bool = True,
) -> TimestampValidationResult:
    if result := require_object(data, "TIMESTAMP_TOKEN_SCHEMA_INVALID", "timestamp token"):
        return result
    if result := require_fields(data, TOKEN_REQUIRED_FIELDS, "TIMESTAMP_TOKEN_SCHEMA_INVALID"):
        return result
    if data.get("timestamp_token_version") != TIMESTAMP_TOKEN_VERSION:
        return failure("TIMESTAMP_TOKEN_SCHEMA_INVALID", "unsupported timestamp_token_version")
    if not isinstance(data.get("token_id"), str) or not data["token_id"]:
        return failure("TIMESTAMP_TOKEN_SCHEMA_INVALID", "token_id must be a non-empty string")
    target = data.get("target")
    if not isinstance(target, dict):
        return failure("TIMESTAMP_TOKEN_SCHEMA_INVALID", "target must be an object")
    if result := require_fields(target, ("target_type", "target_hash", "target_canonicalization"), "TIMESTAMP_TOKEN_SCHEMA_INVALID"):
        return result
    if target.get("target_type") not in KNOWN_TARGET_TYPES:
        return failure("TIMESTAMP_TOKEN_INVALID", "target_type must be a known timestamp target")
    if not is_sha256_ref(target.get("target_hash")):
        return failure("TIMESTAMP_TOKEN_SCHEMA_INVALID", "target_hash must be sha256:<64 lowercase hex>")
    if not isinstance(target.get("target_canonicalization"), str) or not target["target_canonicalization"]:
        return failure("TIMESTAMP_TOKEN_SCHEMA_INVALID", "target_canonicalization must be non-empty")
    if result := validate_utc_z_timestamp(data.get("claimed_time")):
        return result
    time_source = data.get("time_source")
    if not isinstance(time_source, dict):
        return failure("TIMESTAMP_TOKEN_SCHEMA_INVALID", "time_source must be an object")
    if result := require_fields(time_source, ("source_type", "authority_id"), "TIMESTAMP_TOKEN_SCHEMA_INVALID"):
        return result
    if time_source.get("source_type") not in {"local_clock", "mock", "tsa"}:
        return failure("TIMESTAMP_TOKEN_SCHEMA_INVALID", "unsupported time_source.source_type")
    if not isinstance(data.get("metadata"), dict):
        return failure("TIMESTAMP_TOKEN_SCHEMA_INVALID", "metadata must be an object")

    if strict_current_alpha:
        if data.get("token_kind") != SUPPORTED_TOKEN_KIND:
            return failure("TIMESTAMP_TOKEN_INVALID", "CURRENT_ALPHA supports token_kind mock_local only")
        if data.get("trusted_time_claimed") is not False:
            return failure(
                "TIMESTAMP_TRUSTED_TIME_UNSUPPORTED",
                "CURRENT_ALPHA mock/local timestamp tokens must not claim trusted time",
            )
        if time_source.get("source_type") == "tsa":
            return failure("TIMESTAMP_TSA_UNSUPPORTED", "CURRENT_ALPHA does not validate TSA timestamp tokens")
        if data.get("signature") is not None:
            return failure("TIMESTAMP_SIGNATURE_UNSUPPORTED", "mock_local tokens must not include signatures")
    return TimestampValidationResult(ok=True)


def verify_timestamp_token_binding(token: dict[str, Any], target_hash: str) -> TimestampValidationResult:
    validation = validate_timestamp_token(token)
    if not validation.ok:
        return validation
    if not is_sha256_ref(target_hash):
        return failure("TIMESTAMP_TARGET_HASH_MISMATCH", "target_hash argument must be sha256:<64 lowercase hex>")
    token_target_hash = token["target"]["target_hash"]
    if token_target_hash != target_hash:
        return failure(
            "TIMESTAMP_TARGET_HASH_MISMATCH",
            f"timestamp token targets {token_target_hash}, not {target_hash}",
        )
    return TimestampValidationResult(ok=True)


def inspect_timestamp_token(data: dict[str, Any] | None) -> TimestampInspection:
    if data is None:
        return TimestampInspection("not_present", False, None, None, None, "no timestamp token present")
    validation = validate_timestamp_token(data)
    if not validation.ok:
        target = data.get("target") if isinstance(data, dict) else {}
        return TimestampInspection(
            "invalid",
            bool(data.get("trusted_time_claimed")) if isinstance(data, dict) else False,
            data.get("token_kind") if isinstance(data, dict) else None,
            target.get("target_type") if isinstance(target, dict) else None,
            target.get("target_hash") if isinstance(target, dict) else None,
            validation.message or "timestamp token invalid",
        )
    return TimestampInspection(
        "mock",
        False,
        data["token_kind"],
        data["target"]["target_type"],
        data["target"]["target_hash"],
        "valid mock/local timestamp token; no trusted timestamp proof is claimed",
    )

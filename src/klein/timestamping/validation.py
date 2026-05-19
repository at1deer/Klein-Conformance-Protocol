"""Shared validation helpers for timestamp profile/token stubs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class TimestampValidationError(ValueError):
    """Structured timestamp validation failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class TimestampValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None


def failure(error_code: str, message: str) -> TimestampValidationResult:
    return TimestampValidationResult(ok=False, error_code=error_code, message=message)


def require_object(data: Any, error_code: str, label: str) -> TimestampValidationResult | None:
    if not isinstance(data, dict):
        return failure(error_code, f"{label} root must be an object")
    return None


def require_fields(data: dict[str, Any], fields: tuple[str, ...], error_code: str) -> TimestampValidationResult | None:
    for field in fields:
        if field not in data:
            return failure(error_code, f"missing required field {field}")
    return None


def is_sha256_ref(value: Any) -> bool:
    return isinstance(value, str) and SHA256_REF_RE.fullmatch(value) is not None


def validate_utc_z_timestamp(value: Any) -> TimestampValidationResult | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.endswith("Z"):
        return failure("TIMESTAMP_TIME_INVALID", "claimed_time must be a UTC timestamp ending in Z")
    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return failure("TIMESTAMP_TIME_INVALID", "claimed_time must be parseable RFC3339-style UTC")
    return None

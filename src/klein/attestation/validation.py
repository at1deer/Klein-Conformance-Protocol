"""Shared validation helpers for attestation profile/statement stubs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

SHA256_REF_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class AttestationValidationError(ValueError):
    """Structured attestation validation failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class AttestationValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None


def failure(error_code: str, message: str) -> AttestationValidationResult:
    return AttestationValidationResult(ok=False, error_code=error_code, message=message)


def require_object(data: Any, error_code: str, label: str) -> AttestationValidationResult | None:
    if not isinstance(data, dict):
        return failure(error_code, f"{label} root must be an object")
    return None


def require_fields(data: dict[str, Any], fields: tuple[str, ...], error_code: str) -> AttestationValidationResult | None:
    for field in fields:
        if field not in data:
            return failure(error_code, f"missing required field {field}")
    return None


def is_sha256_ref(value: Any) -> bool:
    return isinstance(value, str) and SHA256_REF_RE.fullmatch(value) is not None

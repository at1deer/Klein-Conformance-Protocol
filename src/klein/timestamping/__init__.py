"""Trusted Timestamp Profile v1 stub utilities."""

from klein.timestamping.profile import (
    TIMESTAMP_PROFILE_VERSION,
    canonical_timestamp_profile_hash,
    validate_timestamp_profile,
)
from klein.timestamping.token import (
    TIMESTAMP_TOKEN_VERSION,
    TimestampInspection,
    canonical_timestamp_token_hash,
    inspect_timestamp_token,
    validate_timestamp_token,
    verify_timestamp_token_binding,
)
from klein.timestamping.validation import TimestampValidationError, TimestampValidationResult

__all__ = [
    "TIMESTAMP_PROFILE_VERSION",
    "TIMESTAMP_TOKEN_VERSION",
    "TimestampInspection",
    "TimestampValidationError",
    "TimestampValidationResult",
    "canonical_timestamp_profile_hash",
    "canonical_timestamp_token_hash",
    "inspect_timestamp_token",
    "validate_timestamp_profile",
    "validate_timestamp_token",
    "verify_timestamp_token_binding",
]

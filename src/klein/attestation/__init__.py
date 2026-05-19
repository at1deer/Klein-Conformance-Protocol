"""Attestation Profile v1 stub utilities."""

from klein.attestation.profile import (
    ATTESTATION_PROFILE_VERSION,
    canonical_attestation_profile_hash,
    validate_attestation_profile,
)
from klein.attestation.statement import (
    ATTESTATION_STATEMENT_VERSION,
    AttestationInspection,
    canonical_attestation_statement_hash,
    inspect_attestation_statement,
    validate_attestation_statement,
    verify_attestation_statement_binding,
)
from klein.attestation.validation import AttestationValidationError, AttestationValidationResult

__all__ = [
    "ATTESTATION_PROFILE_VERSION",
    "ATTESTATION_STATEMENT_VERSION",
    "AttestationInspection",
    "AttestationValidationError",
    "AttestationValidationResult",
    "canonical_attestation_profile_hash",
    "canonical_attestation_statement_hash",
    "inspect_attestation_statement",
    "validate_attestation_profile",
    "validate_attestation_statement",
    "verify_attestation_statement_binding",
]

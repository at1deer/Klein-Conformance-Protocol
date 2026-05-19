"""HIL Readiness v1 contract/status validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.common.hashing import HashResult, hash_json_artifact, hash_json_value, parse_ijson

HIL_CONTRACT_VERSION = "klein.hil_backend_contract.v1"
HIL_STATUS_VERSION = "klein.hil_backend_status.v1"
REQUIRED_OPERATIONS = {
    "connect",
    "disconnect",
    "get_capabilities",
    "get_topology",
    "get_health",
    "apply_frame",
    "read_observation",
    "emergency_stop",
    "reset",
}


class HILValidationError(ValueError):
    """Structured HIL readiness validation failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class HILValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None


def load_hil_json(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise HILValidationError("HIL_CONTRACT_SCHEMA_INVALID", "HIL artifact root must be an object")
    return data


def canonical_hil_contract_hash(data_or_path: dict[str, Any] | str | Path) -> HashResult:
    if isinstance(data_or_path, str | Path):
        return hash_json_artifact(Path(data_or_path))
    return hash_json_value(data_or_path)


def validate_hil_backend_contract(data: dict[str, Any]) -> HILValidationResult:
    if data.get("hil_contract_version") != HIL_CONTRACT_VERSION:
        return _failure("HIL_CONTRACT_SCHEMA_INVALID", "unsupported hil_contract_version")
    for field in ("backend_id", "backend_version", "profile", "supports", "observation_sources", "attestation", "safety", "limitations"):
        if field not in data:
            return _failure("HIL_CONTRACT_SCHEMA_INVALID", f"contract missing required field {field}")
    profile = data.get("profile")
    if not isinstance(profile, dict) or not profile.get("profile_id") or not profile.get("profile_version"):
        return _failure("HIL_CONTRACT_SCHEMA_INVALID", "profile must include profile_id and profile_version")
    supports = data.get("supports")
    if not isinstance(supports, dict):
        return _failure("HIL_CONTRACT_SCHEMA_INVALID", "supports must be an object")
    missing = sorted(op for op in REQUIRED_OPERATIONS if supports.get(op) is not True)
    if missing:
        if "emergency_stop" in missing:
            return _failure("HIL_ESTOP_REQUIRED", "HIL readiness requires emergency_stop support")
        return _failure("HIL_OPERATION_UNSUPPORTED", f"HIL readiness missing required operations: {', '.join(missing)}")
    safety = data.get("safety")
    if not isinstance(safety, dict):
        return _failure("HIL_CONTRACT_SCHEMA_INVALID", "safety must be an object")
    if safety.get("requires_emergency_stop") is not True:
        return _failure("HIL_ESTOP_REQUIRED", "safety.requires_emergency_stop must be true")
    if safety.get("requires_reset") is not True or supports.get("reset") is not True:
        return _failure("HIL_OPERATION_UNSUPPORTED", "HIL readiness requires reset support")
    attestation = data.get("attestation")
    if not isinstance(attestation, dict):
        return _failure("HIL_CONTRACT_SCHEMA_INVALID", "attestation must be an object")
    if attestation.get("supported") is True or attestation.get("profiles"):
        return _failure("HIL_ATTESTATION_UNSUPPORTED", "attestation is not supported in CURRENT_ALPHA HIL readiness")
    observation_sources = data.get("observation_sources")
    if not isinstance(observation_sources, list) or not observation_sources:
        return _failure("HIL_CONTRACT_SCHEMA_INVALID", "observation_sources must be non-empty")
    if "hardware_sensor" in observation_sources:
        return _failure("HIL_HARDWARE_CLAIM_UNSUPPORTED", "hardware_sensor source is not supported in CURRENT_ALPHA")
    limitations = data.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        return _failure("HIL_CONTRACT_INVALID", "limitations must be non-empty")
    return HILValidationResult(ok=True)


def validate_hil_backend_status(data: dict[str, Any]) -> HILValidationResult:
    if data.get("hil_status_version") != HIL_STATUS_VERSION:
        return _failure("HIL_STATUS_SCHEMA_INVALID", "unsupported hil_status_version")
    for field in ("backend_id", "connected", "health", "emergency_stopped", "last_error_code", "details"):
        if field not in data:
            return _failure("HIL_STATUS_SCHEMA_INVALID", f"status missing required field {field}")
    if data.get("health") not in {"OK", "DEGRADED", "FAULTED", "UNKNOWN"}:
        return _failure("HIL_STATUS_INVALID", "health must be OK, DEGRADED, FAULTED, or UNKNOWN")
    if data.get("health") == "FAULTED" and not data.get("last_error_code"):
        return _failure("HIL_FAULT_MISSING_ERROR", "FAULTED status must include last_error_code")
    return HILValidationResult(ok=True)


def validate_hil_readiness_contract(data: dict[str, Any]) -> HILValidationResult:
    return validate_hil_backend_contract(data)


def _failure(error_code: str, message: str) -> HILValidationResult:
    return HILValidationResult(ok=False, error_code=error_code, message=message)

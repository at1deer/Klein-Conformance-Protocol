"""DMF backend adapter config/status validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.common.hashing import parse_ijson

CONFIG_VERSION = "klein.dmf_backend_adapter_config.v1"
STATUS_VERSION = "klein.dmf_backend_adapter_status.v1"


class DmfAdapterError(ValueError):
    """Structured DMF adapter validation failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class DmfAdapterValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None


def load_dmf_backend_adapter_config(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise DmfAdapterError("DMF_ADAPTER_SCHEMA_INVALID", "adapter config root must be an object")
    return data


def validate_dmf_backend_adapter_config(data: dict[str, Any]) -> DmfAdapterValidationResult:
    if data.get("adapter_config_version") != CONFIG_VERSION:
        return _failure("DMF_ADAPTER_SCHEMA_INVALID", "unsupported adapter_config_version")
    for field in ("adapter_id", "adapter_kind", "backend_id", "backend_version", "profile", "mode", "hardware_io_enabled", "substrate", "safety", "limitations"):
        if field not in data:
            return _failure("DMF_ADAPTER_SCHEMA_INVALID", f"missing required field {field}")
    if data.get("adapter_kind") != "generic_dmf":
        return _failure("DMF_ADAPTER_SCHEMA_INVALID", "adapter_kind must be generic_dmf")
    profile = data.get("profile")
    if not isinstance(profile, dict) or profile.get("profile_id") != "dmf" or profile.get("profile_version") != "v1":
        return _failure("DMF_ADAPTER_PROFILE_UNSUPPORTED", "adapter profile must be dmf/v1")
    if data.get("mode") not in {"dry_run", "mock"}:
        return _failure("DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED", "only dry_run/mock modes are supported in CURRENT_ALPHA")
    if data.get("hardware_io_enabled") is True:
        return _failure("DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED", "hardware_io_enabled must be false in CURRENT_ALPHA")
    safety = data.get("safety")
    if not isinstance(safety, dict):
        return _failure("DMF_ADAPTER_SCHEMA_INVALID", "safety must be an object")
    if safety.get("require_estop") is not True:
        return _failure("DMF_ADAPTER_ESTOP_REQUIRED", "safety.require_estop must be true")
    if safety.get("allow_hardware_io") is True:
        return _failure("DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED", "safety.allow_hardware_io must be false in CURRENT_ALPHA")
    substrate = data.get("substrate")
    if not isinstance(substrate, dict):
        return _failure("DMF_ADAPTER_SCHEMA_INVALID", "substrate must be an object")
    for field in ("grid_width", "grid_height", "max_channels"):
        if not isinstance(substrate.get(field), int) or substrate[field] <= 0:
            return _failure("DMF_ADAPTER_SCHEMA_INVALID", f"substrate.{field} must be positive integer")
    limitations = data.get("limitations")
    if not isinstance(limitations, list) or not limitations:
        return _failure("DMF_ADAPTER_CONFIG_INVALID", "limitations must be non-empty")
    return DmfAdapterValidationResult(ok=True)


def validate_dmf_backend_adapter_status(data: dict[str, Any]) -> DmfAdapterValidationResult:
    if data.get("adapter_status_version") != STATUS_VERSION:
        return _failure("DMF_ADAPTER_STATUS_INVALID", "unsupported adapter_status_version")
    for field in ("adapter_id", "connected", "hardware_io_enabled", "health", "emergency_stopped", "last_error_code"):
        if field not in data:
            return _failure("DMF_ADAPTER_STATUS_INVALID", f"missing required field {field}")
    if data.get("hardware_io_enabled") is True:
        return _failure("DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED", "hardware_io_enabled must be false in CURRENT_ALPHA")
    if data.get("health") not in {"OK", "DEGRADED", "FAULTED", "UNKNOWN"}:
        return _failure("DMF_ADAPTER_STATUS_INVALID", "health is invalid")
    if data.get("health") == "FAULTED" and not data.get("last_error_code"):
        return _failure("DMF_ADAPTER_STATUS_INVALID", "FAULTED status requires last_error_code")
    return DmfAdapterValidationResult(ok=True)


def _failure(error_code: str, message: str) -> DmfAdapterValidationResult:
    return DmfAdapterValidationResult(ok=False, error_code=error_code, message=message)

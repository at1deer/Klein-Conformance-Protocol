"""OpenDrop/EWOD adapter config, status, and intent validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.common.hashing import parse_ijson

CONFIG_VERSION = "klein.opendrop_adapter_config.v1"
STATUS_VERSION = "klein.opendrop_adapter_status.v1"
INTENT_VERSION = "klein.opendrop_command_intent.v1"


class OpenDropAdapterError(ValueError):
    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class OpenDropValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None


def load_opendrop_adapter_config(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise OpenDropAdapterError("OPENDROP_ADAPTER_SCHEMA_INVALID", "config root must be an object")
    return data


def validate_opendrop_adapter_config(data: dict[str, Any]) -> OpenDropValidationResult:
    if data.get("adapter_config_version") != CONFIG_VERSION:
        return _failure("OPENDROP_ADAPTER_SCHEMA_INVALID", "unsupported adapter_config_version")
    for field in ("adapter_id", "adapter_kind", "backend_id", "backend_version", "profile", "mode", "hardware_io_enabled", "transport", "electrode_layout", "electrical_limits", "safety", "limitations"):
        if field not in data:
            return _failure("OPENDROP_ADAPTER_SCHEMA_INVALID", f"missing required field {field}")
    if data.get("adapter_kind") != "opendrop_ewod":
        return _failure("OPENDROP_ADAPTER_SCHEMA_INVALID", "adapter_kind must be opendrop_ewod")
    profile = data.get("profile")
    if not isinstance(profile, dict) or profile.get("profile_id") != "dmf" or profile.get("profile_version") != "v1":
        return _failure("DMF_ADAPTER_PROFILE_UNSUPPORTED", "OpenDrop adapter profile must be dmf/v1")
    if data.get("mode") not in {"dry_run", "mock"}:
        return _failure("OPENDROP_HARDWARE_IO_UNSUPPORTED", "only dry_run/mock modes are supported in CURRENT_ALPHA")
    if data.get("hardware_io_enabled") is True:
        return _failure("OPENDROP_HARDWARE_IO_UNSUPPORTED", "hardware_io_enabled must be false in CURRENT_ALPHA")
    transport = data.get("transport")
    if not isinstance(transport, dict):
        return _failure("OPENDROP_ADAPTER_SCHEMA_INVALID", "transport must be an object")
    if transport.get("transport_kind") != "none" or transport.get("endpoint") is not None:
        return _failure("OPENDROP_TRANSPORT_UNSUPPORTED", "OpenDrop transport must be none/null in CURRENT_ALPHA")
    safety = data.get("safety")
    if not isinstance(safety, dict) or safety.get("require_estop") is not True:
        return _failure("DMF_ADAPTER_ESTOP_REQUIRED", "safety.require_estop must be true")
    if safety.get("allow_hardware_io") is True:
        return _failure("OPENDROP_HARDWARE_IO_UNSUPPORTED", "safety.allow_hardware_io must be false in CURRENT_ALPHA")
    layout_result = _validate_layout(data.get("electrode_layout"))
    if not layout_result.ok:
        return layout_result
    limits = data.get("electrical_limits")
    if not isinstance(limits, dict) or float(limits.get("voltage_min_v", 1)) > float(limits.get("voltage_max_v", 0)):
        return _failure("OPENDROP_ADAPTER_CONFIG_INVALID", "electrical voltage limits are invalid")
    if float(limits.get("frequency_min_hz", 1)) > float(limits.get("frequency_max_hz", 0)):
        return _failure("OPENDROP_ADAPTER_CONFIG_INVALID", "electrical frequency limits are invalid")
    if not isinstance(data.get("limitations"), list) or not data["limitations"]:
        return _failure("OPENDROP_ADAPTER_CONFIG_INVALID", "limitations must be non-empty")
    return OpenDropValidationResult(ok=True)


def validate_opendrop_adapter_status(data: dict[str, Any]) -> OpenDropValidationResult:
    if data.get("adapter_status_version") != STATUS_VERSION:
        return _failure("OPENDROP_ADAPTER_SCHEMA_INVALID", "unsupported adapter_status_version")
    for field in ("adapter_id", "connected", "hardware_io_enabled", "transport_status", "health", "emergency_stopped", "last_error_code"):
        if field not in data:
            return _failure("OPENDROP_ADAPTER_SCHEMA_INVALID", f"missing required field {field}")
    if data.get("hardware_io_enabled") is True:
        return _failure("OPENDROP_HARDWARE_IO_UNSUPPORTED", "hardware_io_enabled must be false in CURRENT_ALPHA")
    if data.get("transport_status") not in {"NONE", "CONNECTED", "DISCONNECTED", "ERROR"}:
        return _failure("OPENDROP_ADAPTER_SCHEMA_INVALID", "transport_status is invalid")
    if data.get("health") not in {"OK", "DEGRADED", "FAULTED", "UNKNOWN"}:
        return _failure("OPENDROP_ADAPTER_SCHEMA_INVALID", "health is invalid")
    if data.get("health") == "FAULTED" and not data.get("last_error_code"):
        return _failure("OPENDROP_ADAPTER_SCHEMA_INVALID", "FAULTED status requires last_error_code")
    return OpenDropValidationResult(ok=True)


def validate_opendrop_command_intent(data: dict[str, Any], *, channel_count: int | None = None) -> OpenDropValidationResult:
    if data.get("command_intent_version") != INTENT_VERSION:
        return _failure("OPENDROP_COMMAND_INTENT_INVALID", "unsupported command_intent_version")
    if data.get("operation") not in {"SET_ELECTRODES", "APPLY_FRAME", "CLEAR_ELECTRODES", "ESTOP", "RESET"}:
        return _failure("OPENDROP_COMMAND_INTENT_INVALID", "unsupported OpenDrop command intent operation")
    electrodes = data.get("electrodes")
    if not isinstance(electrodes, list):
        return _failure("OPENDROP_COMMAND_INTENT_INVALID", "electrodes must be an array")
    for electrode in electrodes:
        if not isinstance(electrode, dict):
            return _failure("OPENDROP_COMMAND_INTENT_INVALID", "electrode intent must be an object")
        channel_id = electrode.get("channel_id")
        if not isinstance(channel_id, int) or channel_id < 1:
            return _failure("OPENDROP_CHANNEL_OOB", "channel_id must be >= 1")
        if channel_count is not None and channel_id > channel_count:
            return _failure("OPENDROP_CHANNEL_OOB", "channel_id exceeds OpenDrop layout channel_count")
        if electrode.get("state") not in {"ON", "OFF"}:
            return _failure("OPENDROP_COMMAND_INTENT_INVALID", "electrode state must be ON or OFF")
    return OpenDropValidationResult(ok=True)


def _validate_layout(layout: Any) -> OpenDropValidationResult:
    if not isinstance(layout, dict):
        return _failure("OPENDROP_MAPPING_INVALID", "electrode_layout must be an object")
    for field in ("grid_width", "grid_height", "channel_count"):
        if not isinstance(layout.get(field), int) or layout[field] <= 0:
            return _failure("OPENDROP_MAPPING_INVALID", f"electrode_layout.{field} must be positive integer")
    if layout.get("mapping") not in {"row_major", "explicit"}:
        return _failure("OPENDROP_MAPPING_INVALID", "mapping must be row_major or explicit")
    if layout.get("mapping") == "explicit":
        explicit = layout.get("explicit_mapping")
        if not isinstance(explicit, list) or not explicit:
            return _failure("OPENDROP_MAPPING_INVALID", "explicit mapping requires explicit_mapping")
        seen_channels: set[int] = set()
        seen_electrodes: set[str] = set()
        seen_coords: set[tuple[int, int]] = set()
        for item in explicit:
            if not isinstance(item, dict):
                return _failure("OPENDROP_MAPPING_INVALID", "explicit mapping entries must be objects")
            channel_id = item.get("channel_id")
            electrode_id = item.get("electrode_id")
            x = item.get("x")
            y = item.get("y")
            if not isinstance(channel_id, int) or channel_id < 1 or channel_id > layout["channel_count"]:
                return _failure("OPENDROP_CHANNEL_OOB", "explicit mapping channel_id out of range")
            if not isinstance(electrode_id, str) or not isinstance(x, int) or not isinstance(y, int):
                return _failure("OPENDROP_MAPPING_INVALID", "explicit mapping entry is invalid")
            coord = (x, y)
            if channel_id in seen_channels or electrode_id in seen_electrodes or coord in seen_coords:
                return _failure("OPENDROP_MAPPING_DUPLICATE", "explicit mapping contains duplicate channel, electrode, or coordinate")
            seen_channels.add(channel_id)
            seen_electrodes.add(electrode_id)
            seen_coords.add(coord)
    return OpenDropValidationResult(ok=True)


def _failure(error_code: str, message: str) -> OpenDropValidationResult:
    return OpenDropValidationResult(ok=False, error_code=error_code, message=message)

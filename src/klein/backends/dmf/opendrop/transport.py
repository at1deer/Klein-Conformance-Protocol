"""OpenDrop transport planning validation.

This module defines planning artifacts only. It does not open serial ports or perform device IO.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.backends.dmf.opendrop.config import OpenDropAdapterError, OpenDropValidationResult
from klein.common.hashing import parse_ijson

TRANSPORT_CONFIG_VERSION = "klein.opendrop_transport_config.v1"
SERIAL_COMMAND_VERSION = "klein.opendrop_serial_command.v1"
TRANSPORT_KINDS = {"none", "serial_experimental"}
COMMAND_ENCODINGS = {"jsonl", "text_lines"}
PROTOCOL_FAMILY = "opendrop_arduino_style"
DEFAULT_TRANSPORT_CONFIG = {
    "transport_config_version": TRANSPORT_CONFIG_VERSION,
    "transport_kind": "none",
    "hardware_io_enabled": False,
    "requires_explicit_enable": True,
    "endpoint": None,
    "baud_rate": None,
    "protocol_family": PROTOCOL_FAMILY,
    "command_encoding": "jsonl",
    "untested_hardware_warning": True,
    "limitations": [
        "Transport planning only.",
        "No OpenDrop hardware support is claimed.",
    ],
}


@dataclass(frozen=True)
class OpenDropTransportInspection:
    transport_kind: str | None
    hardware_io_enabled: bool
    endpoint_present: bool
    transport_status: str
    message: str


def load_opendrop_transport_config(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise OpenDropAdapterError("OPENDROP_TRANSPORT_SCHEMA_INVALID", "OpenDrop transport config root must be an object")
    return data


def validate_opendrop_transport_config(
    data: dict[str, Any],
    *,
    strict_current_alpha: bool = True,
    allow_experimental_hardware_io: bool = False,
) -> OpenDropValidationResult:
    if data.get("transport_config_version") != TRANSPORT_CONFIG_VERSION:
        return _failure("OPENDROP_TRANSPORT_SCHEMA_INVALID", "unsupported transport_config_version")
    for field in (
        "transport_kind",
        "hardware_io_enabled",
        "requires_explicit_enable",
        "endpoint",
        "baud_rate",
        "protocol_family",
        "command_encoding",
        "untested_hardware_warning",
        "limitations",
    ):
        if field not in data:
            return _failure("OPENDROP_TRANSPORT_SCHEMA_INVALID", f"missing required field {field}")
    if data.get("transport_kind") not in TRANSPORT_KINDS:
        return _failure("OPENDROP_TRANSPORT_UNSUPPORTED", "unsupported OpenDrop transport_kind")
    if data.get("protocol_family") != PROTOCOL_FAMILY:
        return _failure("OPENDROP_TRANSPORT_CONFIG_INVALID", "protocol_family must be opendrop_arduino_style")
    if data.get("command_encoding") not in COMMAND_ENCODINGS:
        return _failure("OPENDROP_TRANSPORT_CONFIG_INVALID", "command_encoding must be jsonl or text_lines")
    if data.get("untested_hardware_warning") is not True:
        return _failure("OPENDROP_TRANSPORT_CONFIG_INVALID", "untested_hardware_warning must be true")
    if not isinstance(data.get("limitations"), list) or not data["limitations"]:
        return _failure("OPENDROP_TRANSPORT_CONFIG_INVALID", "limitations must be non-empty")

    if strict_current_alpha:
        if data.get("hardware_io_enabled") is True and not allow_experimental_hardware_io:
            return _failure("OPENDROP_HARDWARE_IO_UNSUPPORTED", "hardware_io_enabled must be false in CURRENT_ALPHA")
        if data.get("transport_kind") == "serial_experimental" and data.get("requires_explicit_enable") is not True:
            return _failure("OPENDROP_TRANSPORT_CONFIG_INVALID", "serial_experimental requires explicit enable")
        if data.get("endpoint") is not None and not allow_experimental_hardware_io:
            return _failure(
                "OPENDROP_ENDPOINT_UNSUPPORTED_CURRENT_ALPHA",
                "OpenDrop endpoint must be null in CURRENT_ALPHA transport planning",
            )
        if data.get("baud_rate") is not None and not allow_experimental_hardware_io:
            return _failure(
                "OPENDROP_ENDPOINT_UNSUPPORTED_CURRENT_ALPHA",
                "OpenDrop baud_rate must be null in CURRENT_ALPHA transport planning",
            )
    return OpenDropValidationResult(ok=True)


def validate_opendrop_serial_command(data: dict[str, Any]) -> OpenDropValidationResult:
    if data.get("serial_command_version") != SERIAL_COMMAND_VERSION:
        return _failure("OPENDROP_SERIAL_COMMAND_INVALID", "unsupported serial_command_version")
    for field in ("command_id", "intent_id", "tick", "command_kind", "encoding", "payload", "raw_line", "hardware_io_allowed"):
        if field not in data:
            return _failure("OPENDROP_SERIAL_COMMAND_INVALID", f"missing required field {field}")
    if data.get("command_kind") not in {"SET_ELECTRODES", "APPLY_FRAME", "CLEAR_ELECTRODES", "ESTOP", "RESET"}:
        return _failure("OPENDROP_SERIAL_COMMAND_INVALID", "unsupported serial command kind")
    if not isinstance(data.get("tick"), int) or data["tick"] < 0:
        return _failure("OPENDROP_SERIAL_COMMAND_INVALID", "tick must be a non-negative integer")
    if data.get("encoding") not in {"json", "text"}:
        return _failure("OPENDROP_SERIAL_COMMAND_INVALID", "encoding must be json or text")
    if not isinstance(data.get("payload"), dict):
        return _failure("OPENDROP_SERIAL_COMMAND_INVALID", "payload must be an object")
    if not isinstance(data.get("raw_line"), str) or not data["raw_line"]:
        return _failure("OPENDROP_SERIAL_COMMAND_INVALID", "raw_line must be non-empty")
    if data.get("hardware_io_allowed") is not False:
        return _failure("OPENDROP_HARDWARE_IO_UNSUPPORTED", "serialized commands must not allow hardware IO in CURRENT_ALPHA")
    return OpenDropValidationResult(ok=True)


def inspect_transport_config(data: dict[str, Any]) -> OpenDropTransportInspection:
    result = validate_opendrop_transport_config(data)
    if not result.ok:
        return OpenDropTransportInspection(
            data.get("transport_kind") if isinstance(data, dict) else None,
            bool(data.get("hardware_io_enabled")) if isinstance(data, dict) else False,
            data.get("endpoint") is not None if isinstance(data, dict) else False,
            "invalid",
            result.message or "OpenDrop transport config invalid",
        )
    return OpenDropTransportInspection(
        data["transport_kind"],
        bool(data["hardware_io_enabled"]),
        data.get("endpoint") is not None,
        "planning_only",
        "OpenDrop transport planning only; hardware_io_enabled=false; no device IO performed",
    )


def _failure(error_code: str, message: str) -> OpenDropValidationResult:
    return OpenDropValidationResult(ok=False, error_code=error_code, message=message)

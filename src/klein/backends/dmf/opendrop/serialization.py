"""Deterministic OpenDrop command-stream serialization for dry-run transport planning."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

from klein.backends.dmf.opendrop.config import (
    OpenDropAdapterError,
    validate_opendrop_command_intent,
)
from klein.backends.dmf.opendrop.transport import (
    SERIAL_COMMAND_VERSION,
    validate_opendrop_serial_command,
    validate_opendrop_transport_config,
)


def serialize_intent_to_opendrop_command(intent: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    _require_valid_transport(config)
    result = validate_opendrop_command_intent(intent)
    if not result.ok:
        raise OpenDropAdapterError(result.error_code or "OPENDROP_COMMAND_INTENT_INVALID", result.message or "invalid OpenDrop command intent")

    command_kind = str(intent["operation"])
    encoding = "json" if config.get("command_encoding") == "jsonl" else "text"
    payload = {
        "command": command_kind,
        "electrodes": intent.get("electrodes", []),
        "tick": intent["tick"],
    }
    command = {
        "serial_command_version": SERIAL_COMMAND_VERSION,
        "command_id": _command_id_from_intent(intent),
        "intent_id": intent["intent_id"],
        "tick": intent["tick"],
        "command_kind": command_kind,
        "encoding": encoding,
        "payload": payload,
        "raw_line": _raw_line(payload, encoding),
        "hardware_io_allowed": False,
    }
    serial_result = validate_opendrop_serial_command(command)
    if not serial_result.ok:
        raise OpenDropAdapterError(serial_result.error_code or "OPENDROP_SERIALIZATION_FAILED", serial_result.message or "invalid serialized OpenDrop command")
    return command


def serialize_intents_to_command_stream(intents: Iterable[dict[str, Any]], config: dict[str, Any]) -> str:
    commands = [serialize_intent_to_opendrop_command(intent, config) for intent in intents]
    return "".join(_canonical_json(command) + "\n" for command in commands)


def _require_valid_transport(config: dict[str, Any]) -> None:
    result = validate_opendrop_transport_config(config)
    if not result.ok:
        raise OpenDropAdapterError(result.error_code or "OPENDROP_TRANSPORT_CONFIG_INVALID", result.message or "invalid OpenDrop transport config")


def _command_id_from_intent(intent: dict[str, Any]) -> str:
    suffix = str(intent["intent_id"]).removeprefix("intent-")
    return f"cmd-{suffix}"


def _raw_line(payload: dict[str, Any], encoding: str) -> str:
    if encoding == "json":
        return _canonical_json(payload)
    electrodes = payload.get("electrodes", [])
    channels = ",".join(str(electrode.get("channel_id")) for electrode in electrodes if isinstance(electrode, dict))
    return f"{payload['command']} tick={payload['tick']} channels={channels}"


def _canonical_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

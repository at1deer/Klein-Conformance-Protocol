"""OpenDrop/EWOD electrode mapping and command-intent generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from klein.backends.dmf.opendrop.config import (
    INTENT_VERSION,
    OpenDropAdapterError,
    validate_opendrop_command_intent,
)
from klein.substrate.api import Frame


@dataclass(frozen=True)
class OpenDropElectrode:
    channel_id: int
    electrode_id: str
    x: int
    y: int


def build_electrode_mapping(config: dict[str, Any]) -> dict[int, OpenDropElectrode]:
    layout = config["electrode_layout"]
    width = int(layout["grid_width"])
    height = int(layout["grid_height"])
    channel_count = int(layout["channel_count"])
    if width * height < channel_count:
        raise OpenDropAdapterError("OPENDROP_MAPPING_INVALID", "grid dimensions cannot contain channel_count")
    if layout.get("mapping") == "explicit":
        return _explicit_mapping(layout, width, height, channel_count)
    return {
        channel_id: OpenDropElectrode(
            channel_id=channel_id,
            electrode_id=f"E{channel_id:04d}",
            x=(channel_id - 1) % width,
            y=(channel_id - 1) // width,
        )
        for channel_id in range(1, channel_count + 1)
    }


def dmf_frame_to_opendrop_intent(
    frame: Frame,
    mapping: dict[int, OpenDropElectrode],
    electrical_context: dict[str, Any],
    *,
    operation: str = "APPLY_FRAME",
    intent_id: str | None = None,
) -> dict[str, Any]:
    tick = int(frame.tags.get("tick", frame.seq - 1))
    electrodes = []
    for zero_based_channel in frame.active_electrodes:
        channel_id = int(zero_based_channel) + 1
        electrode = mapping.get(channel_id)
        if electrode is None:
            raise OpenDropAdapterError("OPENDROP_CHANNEL_OOB", f"channel_id {channel_id} is outside OpenDrop layout")
        electrodes.append(_electrode_intent(electrode, "ON", electrical_context))
    intent = {
        "command_intent_version": INTENT_VERSION,
        "intent_id": intent_id or f"intent-{frame.seq:04d}",
        "tick": tick,
        "operation": operation,
        "electrodes": electrodes,
        "metadata": {
            "source_runbook_step_id": frame.tags.get("runbook_step_id"),
            "source_operation": frame.tags.get("operation"),
        },
    }
    result = validate_opendrop_command_intent(intent, channel_count=len(mapping))
    if not result.ok:
        raise OpenDropAdapterError(result.error_code or "OPENDROP_COMMAND_INTENT_INVALID", result.message or "invalid OpenDrop command intent")
    return intent


def runbook_step_to_opendrop_intent(
    step: dict[str, Any],
    mapping: dict[int, OpenDropElectrode],
    context: dict[str, Any],
    *,
    seq: int,
) -> dict[str, Any]:
    details = step.get("expected_effect", {}).get("details", {})
    if isinstance(details, dict):
        frame_format = details.get("frame_format")
        if frame_format is not None and frame_format != "sparse":
            raise OpenDropAdapterError("OPENDROP_COMMAND_INTENT_INVALID", f"unsupported OpenDrop dry-run frame_format: {frame_format}")
    channels = details.get("active_channels") if isinstance(details, dict) else None
    if not isinstance(channels, list):
        channels = [int(step.get("tick", seq - 1)) % len(mapping)]
    frame = Frame(
        seq=seq,
        active_electrodes=tuple(int(channel) for channel in channels if isinstance(channel, int)),
        duration_ms=10,
        tags={"tick": step.get("tick", seq - 1), "runbook_step_id": step.get("step_id"), "operation": step.get("operation")},
    )
    return dmf_frame_to_opendrop_intent(
        frame,
        mapping,
        context,
        operation=_operation_for_step(step),
        intent_id=f"intent-{seq:04d}",
    )


def _operation_for_step(step: dict[str, Any]) -> str:
    operation = str(step.get("operation", "")).upper()
    if "FRAME" in operation:
        return "APPLY_FRAME"
    return "SET_ELECTRODES"


def _electrode_intent(electrode: OpenDropElectrode, state: str, electrical_context: dict[str, Any]) -> dict[str, Any]:
    voltage = electrical_context.get("voltage_v", electrical_context.get("voltage_default_v", 120))
    frequency = electrical_context.get("frequency_hz", electrical_context.get("frequency_default_hz", 1000))
    return {
        "electrode_id": electrode.electrode_id,
        "channel_id": electrode.channel_id,
        "x": electrode.x,
        "y": electrode.y,
        "state": state,
        "voltage_v": voltage,
        "frequency_hz": frequency,
    }


def _explicit_mapping(layout: dict[str, Any], width: int, height: int, channel_count: int) -> dict[int, OpenDropElectrode]:
    mapping: dict[int, OpenDropElectrode] = {}
    seen_electrodes: set[str] = set()
    seen_coords: set[tuple[int, int]] = set()
    for item in layout["explicit_mapping"]:
        channel_id = int(item["channel_id"])
        electrode_id = str(item["electrode_id"])
        x = int(item["x"])
        y = int(item["y"])
        coord = (x, y)
        if channel_id < 1 or channel_id > channel_count or x < 0 or y < 0 or x >= width or y >= height:
            raise OpenDropAdapterError("OPENDROP_CHANNEL_OOB", "explicit mapping entry is outside layout")
        if channel_id in mapping or electrode_id in seen_electrodes or coord in seen_coords:
            raise OpenDropAdapterError("OPENDROP_MAPPING_DUPLICATE", "explicit mapping contains duplicate channel, electrode, or coordinate")
        mapping[channel_id] = OpenDropElectrode(channel_id=channel_id, electrode_id=electrode_id, x=x, y=y)
        seen_electrodes.add(electrode_id)
        seen_coords.add(coord)
    return mapping

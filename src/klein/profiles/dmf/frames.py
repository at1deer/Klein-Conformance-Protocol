"""DMF/EWOD v1 payload-to-frame conversion."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from klein.profiles.dmf.capabilities import DMFProfileContext
from klein.profiles.dmf.validation import decode_bitmap, pixel_to_electrode
from klein.substrate.api import Frame, WaveformMode, WaveformProfile


def dmf_payload_to_frames(
    *,
    kind: Any,
    data: Any,
    context: DMFProfileContext,
    next_seq: Callable[[], int],
    default_duration_ms: int,
) -> list[Frame]:
    kind_value = kind.value if hasattr(kind, "value") else str(kind)
    if kind_value == "CHANNEL_LIST":
        return _channel_list_to_frames(data, next_seq, default_duration_ms)
    if kind_value == "FRAME_SEQUENCE":
        return _frame_sequence_to_frames(data, context, next_seq, default_duration_ms)
    if kind_value == "BITMAP_SEQUENCE":
        return _bitmap_sequence_to_frames(data, context, next_seq, default_duration_ms)
    return []


def _channel_list_to_frames(
    data: list[dict[str, Any]],
    next_seq: Callable[[], int],
    default_duration_ms: int,
) -> list[Frame]:
    if not data:
        return []

    ticks: dict[int, list[dict[str, Any]]] = {}
    for entry in data:
        ticks.setdefault(entry["t"], []).append(entry)

    frames: list[Frame] = []
    for tick in sorted(ticks):
        entries = ticks[tick]
        active = tuple(entry["channel_id"] for entry in entries if entry["state"] == "ON")
        wf_override = None
        if entries:
            first = entries[0]
            frequency = first.get("frequency_hz")
            wf_override = WaveformProfile(
                mode=WaveformMode.AC if frequency is not None else WaveformMode.DC,
                voltage_v=float(first["voltage_v"]),
                ac_frequency_hz=float(frequency) if frequency is not None else None,
            )
        frames.append(Frame(
            seq=next_seq(),
            active_electrodes=active,
            duration_ms=default_duration_ms,
            wf_override=wf_override,
            tags={"tick": tick, "entries": len(entries)},
        ))
    return frames


def _frame_sequence_to_frames(
    data: list[dict[str, Any]],
    context: DMFProfileContext,
    next_seq: Callable[[], int],
    default_duration_ms: int,
) -> list[Frame]:
    if not data:
        return []

    frames: list[Frame] = []
    delta_state: set[int] = set()
    for entry in sorted(data, key=lambda item: item["t"]):
        frame_format = entry["format"]
        if frame_format == "sparse":
            active = tuple(_pixels_to_electrodes(entry["data"], context))
        elif frame_format == "bitmap":
            active = tuple(_bitmap_to_electrodes(entry["data"], context, index=entry["t"]))
        elif frame_format == "delta_tiles":
            active = tuple(_apply_delta_tiles(entry["data"], context, delta_state))
        else:
            raise ValueError(f"Unsupported DMF frame format after validation: {frame_format}")

        frames.append(Frame(
            seq=next_seq(),
            active_electrodes=active,
            duration_ms=default_duration_ms,
            tags={"tick": entry["t"], "format": frame_format},
        ))
    return frames


def _bitmap_sequence_to_frames(
    data: list[Any],
    context: DMFProfileContext,
    next_seq: Callable[[], int],
    default_duration_ms: int,
) -> list[Frame]:
    frames: list[Frame] = []
    for index, bitmap_data in enumerate(data):
        frames.append(Frame(
            seq=next_seq(),
            active_electrodes=tuple(_bitmap_to_electrodes(bitmap_data, context, index=index)),
            duration_ms=default_duration_ms,
            tags={"frame_index": index},
        ))
    return frames


def _pixels_to_electrodes(
    pixels: list[Any],
    context: DMFProfileContext,
) -> list[int]:
    electrodes: list[int] = []
    for pixel in pixels:
        electrode, error = pixel_to_electrode(pixel, context)
        if error is not None:
            raise ValueError(error.code.value)
        assert electrode is not None
        electrodes.append(electrode)
    return electrodes


def _bitmap_to_electrodes(
    bitmap_data: Any,
    context: DMFProfileContext,
    *,
    index: int,
) -> list[int]:
    bitmap, errors = decode_bitmap(bitmap_data, context, index=index)
    if errors:
        raise ValueError(errors[0].code.value)
    assert bitmap is not None
    active: list[int] = []
    for byte_idx, byte in enumerate(bitmap):
        for bit in range(8):
            electrode = byte_idx * 8 + bit
            if electrode >= context.max_channels:
                break
            if byte & (1 << bit):
                active.append(electrode)
    return active


def _apply_delta_tiles(
    delta: dict[str, Any],
    context: DMFProfileContext,
    active_state: set[int],
) -> list[int]:
    add = set(_pixels_to_electrodes(delta.get("add", []), context))
    remove = set(_pixels_to_electrodes(delta.get("remove", []), context))
    active_state.difference_update(remove)
    active_state.update(add)
    return sorted(active_state)


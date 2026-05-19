"""DMF/EWOD v1 payload validation."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass, field
from typing import Any

from klein.common.errors import ErrorCode
from klein.profiles.dmf.capabilities import DMFProfileContext


@dataclass
class PayloadValidationError:
    """Validation error emitted by a DMF profile validator."""

    code: ErrorCode
    message: str
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DmfPayloadValidationResult:
    """Validation result for a DMF/EWOD payload."""

    ok: bool
    errors: list[PayloadValidationError] = field(default_factory=list)


@dataclass(frozen=True)
class DmfFrameValidationResult:
    """Validation result for a DMF/EWOD frame."""

    ok: bool
    errors: list[PayloadValidationError] = field(default_factory=list)


def validate_dmf_payload_result(
    payload: dict[str, Any],
    context: DMFProfileContext,
) -> DmfPayloadValidationResult:
    """Validate a payload and return a structured result object."""
    errors = validate_dmf_payload(payload, context)
    return DmfPayloadValidationResult(ok=not errors, errors=errors)


def validate_dmf_frame(
    frame: dict[str, Any],
    context: DMFProfileContext,
) -> DmfFrameValidationResult:
    """Validate one `FRAME_SEQUENCE` frame entry."""
    errors = _validate_frame_sequence([frame], context)
    return DmfFrameValidationResult(ok=not errors, errors=errors)


def validate_dmf_payload(
    payload: dict[str, Any],
    context: DMFProfileContext,
) -> list[PayloadValidationError]:
    """Validate a DMF/EWOD v1 payload against declared substrate bounds."""
    kind = payload.get("kind")
    if kind not in {"CHANNEL_LIST", "FRAME_SEQUENCE", "BITMAP_SEQUENCE"}:
        return [_error(ErrorCode.DDI_UNSUPPORTED_PAYLOAD, f"Unsupported payload kind {kind}", {"kind": kind})]

    encoding = payload.get("encoding", "JSON")
    if encoding not in {"JSON", "BASE64_GZIP"}:
        return [_error(
            ErrorCode.PAYLOAD_UNSUPPORTED_FRAME_FORMAT,
            f"Unsupported DMF v1 payload encoding {encoding}",
            {"encoding": encoding},
        )]

    data = payload.get("data")
    if kind == "CHANNEL_LIST":
        return _validate_channel_list(data, context)
    if kind == "FRAME_SEQUENCE":
        return _validate_frame_sequence(data, context)
    return _validate_bitmap_sequence(data, context)


def pixel_to_electrode(
    pixel: Any,
    context: DMFProfileContext,
) -> tuple[int | None, PayloadValidationError | None]:
    """Convert an electrode id or x/y coordinate to a declared electrode id."""
    if type(pixel) is int:
        if 0 <= pixel < context.max_channels:
            return pixel, None
        return None, _error(
            ErrorCode.PAYLOAD_OOB_PIXEL,
            f"Sparse electrode id out of range: {pixel}",
            {"pixel": pixel, "max_channels": context.max_channels},
        )

    if isinstance(pixel, dict):
        x = pixel.get("x")
        y = pixel.get("y")
    elif isinstance(pixel, list) and len(pixel) == 2:
        x, y = pixel
    else:
        return None, _error(
            ErrorCode.PAYLOAD_MALFORMED,
            "Sparse pixel must be an electrode id or x/y coordinate",
            {"pixel": pixel},
        )

    if type(x) is not int or type(y) is not int:
        return None, _error(
            ErrorCode.PAYLOAD_MALFORMED,
            "Sparse coordinate x/y must be integers",
            {"pixel": pixel},
        )
    if x < 0 or y < 0 or x >= context.grid_width or y >= context.grid_height:
        return None, _error(
            ErrorCode.PAYLOAD_OOB_PIXEL,
            f"Sparse coordinate out of range: ({x}, {y})",
            {"x": x, "y": y, "grid_width": context.grid_width, "grid_height": context.grid_height},
        )

    electrode = y * context.grid_width + x
    if electrode >= context.max_channels:
        return None, _error(
            ErrorCode.PAYLOAD_OOB_PIXEL,
            f"Sparse coordinate maps to unavailable electrode {electrode}",
            {"electrode": electrode, "max_channels": context.max_channels},
        )
    return electrode, None


def decode_bitmap(
    data: Any,
    context: DMFProfileContext,
    *,
    index: int,
) -> tuple[bytes | None, list[PayloadValidationError]]:
    """Decode a strict base64 bitmap and verify it fits the substrate."""
    if not isinstance(data, str):
        return None, [_error(ErrorCode.PAYLOAD_MALFORMED, "Bitmap data must be base64 text", {"index": index})]
    try:
        decoded = base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as exc:
        return None, [_error(ErrorCode.PAYLOAD_BASE64_INVALID, f"Invalid bitmap base64: {exc}", {"index": index})]
    if len(decoded) * 8 > context.max_channels:
        return None, [_error(
            ErrorCode.PAYLOAD_UNSUPPORTED_DIMS,
            "Bitmap payload expands beyond available electrodes",
            {"index": index, "bits": len(decoded) * 8, "max_channels": context.max_channels},
        )]
    return decoded, []


def _validate_channel_list(data: Any, context: DMFProfileContext) -> list[PayloadValidationError]:
    if not isinstance(data, list):
        return [_error(ErrorCode.PAYLOAD_MALFORMED, "CHANNEL_LIST data must be a list")]

    seen: dict[tuple[int, int], str] = {}
    for index, entry in enumerate(data):
        if not isinstance(entry, dict):
            return [_error(ErrorCode.PAYLOAD_MALFORMED, "CHANNEL_LIST entries must be objects", {"index": index})]
        for key in ("t", "channel_id", "state", "voltage_v"):
            if key not in entry:
                return [_error(
                    ErrorCode.PAYLOAD_MALFORMED,
                    f"CHANNEL_LIST entry missing required field {key}",
                    {"index": index, "field": key},
                )]

        tick_error = _validate_tick(entry["t"], {"index": index, "field": "t"})
        if tick_error:
            return [tick_error]
        channel_error = _validate_channel_id(entry["channel_id"], context, {"index": index, "field": "channel_id"})
        if channel_error:
            return [channel_error]

        state = entry["state"]
        if state not in {"ON", "OFF"}:
            return [_error(ErrorCode.PAYLOAD_INVALID_STATE, f"Invalid channel state {state}", {"index": index})]

        voltage = entry["voltage_v"]
        if (
            isinstance(voltage, bool)
            or not isinstance(voltage, (int, float))
            or not context.voltage_min_v <= float(voltage) <= context.voltage_max_v
        ):
            return [_error(
                ErrorCode.PAYLOAD_VOLTAGE_OOB,
                f"Voltage out of range: {voltage}",
                {"index": index, "voltage_v": voltage, "min": context.voltage_min_v, "max": context.voltage_max_v},
            )]

        frequency = entry.get("frequency_hz")
        if frequency is not None and (
            isinstance(frequency, bool)
            or not isinstance(frequency, (int, float))
            or not context.frequency_min_hz <= float(frequency) <= context.frequency_max_hz
        ):
            return [_error(
                ErrorCode.PAYLOAD_FREQUENCY_OOB,
                f"Frequency out of range: {frequency}",
                {
                    "index": index,
                    "frequency_hz": frequency,
                    "min": context.frequency_min_hz,
                    "max": context.frequency_max_hz,
                },
            )]

        key = (entry["t"], entry["channel_id"])
        previous = seen.get(key)
        if previous is not None and previous != state:
            return [_error(
                ErrorCode.PAYLOAD_CONFLICTING_STATE,
                "Conflicting channel state for the same tick/channel",
                {"index": index, "t": entry["t"], "channel_id": entry["channel_id"]},
            )]
        seen[key] = state
    return []


def _validate_frame_sequence(data: Any, context: DMFProfileContext) -> list[PayloadValidationError]:
    if not isinstance(data, list):
        return [_error(ErrorCode.PAYLOAD_MALFORMED, "FRAME_SEQUENCE data must be a list")]

    active_delta_state: set[int] = set()
    indexed_entries = list(enumerate(data))
    indexed_entries.sort(key=lambda pair: pair[1].get("t", -1) if isinstance(pair[1], dict) else -1)
    for index, entry in indexed_entries:
        if not isinstance(entry, dict):
            return [_error(ErrorCode.PAYLOAD_MALFORMED, "FRAME_SEQUENCE entries must be objects", {"index": index})]
        for key in ("t", "format", "data"):
            if key not in entry:
                return [_error(
                    ErrorCode.PAYLOAD_MALFORMED,
                    "FRAME_SEQUENCE entry missing t, format, or data",
                    {"index": index, "field": key},
                )]
        tick_error = _validate_tick(entry["t"], {"index": index, "field": "t"})
        if tick_error:
            return [tick_error]

        frame_format = entry["format"]
        if frame_format == "sparse":
            errors, _ = _validate_sparse_pixels(entry["data"], context, index=index)
            if errors:
                return errors
        elif frame_format == "bitmap":
            _, errors = decode_bitmap(entry["data"], context, index=index)
            if errors:
                return errors
        elif frame_format == "delta_tiles":
            errors = _validate_delta_tiles(entry["data"], context, index=index, active_state=active_delta_state)
            if errors:
                return errors
        elif frame_format == "rle":
            return [_error(
                ErrorCode.PAYLOAD_UNSUPPORTED_FRAME_FORMAT,
                "FRAME_SEQUENCE format rle is not supported in DMF v1 alpha",
                {"index": index, "format": frame_format},
            )]
        else:
            return [_error(
                ErrorCode.PAYLOAD_MALFORMED,
                f"Unsupported frame format {frame_format}",
                {"index": index, "format": frame_format},
            )]
    return []


def _validate_bitmap_sequence(data: Any, context: DMFProfileContext) -> list[PayloadValidationError]:
    if not isinstance(data, list):
        return [_error(ErrorCode.PAYLOAD_MALFORMED, "BITMAP_SEQUENCE data must be a list")]
    for index, bitmap_data in enumerate(data):
        _, errors = decode_bitmap(bitmap_data, context, index=index)
        if errors:
            return errors
    return []


def _validate_delta_tiles(
    data: Any,
    context: DMFProfileContext,
    *,
    index: int,
    active_state: set[int],
) -> list[PayloadValidationError]:
    if not isinstance(data, dict):
        return [_error(ErrorCode.PAYLOAD_MALFORMED, "delta_tiles data must be an object", {"index": index})]
    add = data.get("add", [])
    remove = data.get("remove", [])
    add_errors, add_electrodes = _validate_sparse_pixels(add, context, index=index)
    if add_errors:
        return add_errors
    remove_errors, remove_electrodes = _validate_sparse_pixels(remove, context, index=index)
    if remove_errors:
        return remove_errors
    conflict = add_electrodes & remove_electrodes
    if conflict:
        return [_error(
            ErrorCode.PAYLOAD_DELTA_CONFLICT,
            "delta_tiles add/remove conflict",
            {"index": index, "electrodes": sorted(conflict)},
        )]
    missing = remove_electrodes - active_state
    if missing:
        return [_error(
            ErrorCode.PAYLOAD_DELTA_REMOVE_MISS,
            "delta_tiles remove references inactive electrodes",
            {"index": index, "electrodes": sorted(missing)},
        )]
    active_state.difference_update(remove_electrodes)
    active_state.update(add_electrodes)
    return []


def _validate_sparse_pixels(
    pixels: Any,
    context: DMFProfileContext,
    *,
    index: int,
) -> tuple[list[PayloadValidationError], set[int]]:
    if not isinstance(pixels, list):
        return [_error(ErrorCode.PAYLOAD_MALFORMED, "Sparse frame data must be a list", {"index": index})], set()

    seen: set[int] = set()
    for pixel in pixels:
        electrode, error = pixel_to_electrode(pixel, context)
        if error is not None:
            return [error], set()
        assert electrode is not None
        if electrode in seen:
            return [_error(
                ErrorCode.PAYLOAD_DUPLICATE_PIXEL,
                f"Duplicate sparse electrode {electrode}",
                {"index": index, "electrode": electrode},
            )], set()
        seen.add(electrode)
    return [], seen


def _validate_tick(value: Any, detail: dict[str, Any]) -> PayloadValidationError | None:
    if type(value) is not int or value < 0:
        return _error(ErrorCode.PAYLOAD_MALFORMED, "Payload tick must be an integer >= 0", detail)
    return None


def _validate_channel_id(
    value: Any,
    context: DMFProfileContext,
    detail: dict[str, Any],
) -> PayloadValidationError | None:
    if type(value) is not int or value < 0 or value >= context.max_channels:
        return _error(
            ErrorCode.PAYLOAD_CHANNEL_OOB,
            f"Payload channel out of range: {value}",
            {**detail, "max_channels": context.max_channels},
        )
    return None


def _error(
    code: ErrorCode,
    message: str,
    detail: dict[str, Any] | None = None,
) -> PayloadValidationError:
    return PayloadValidationError(code=code, message=message, detail=detail or {})

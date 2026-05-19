"""DMF/EWOD v1 payload adapter."""

from __future__ import annotations

import base64
import gzip
import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from klein.common.errors import ErrorCode
from klein.profiles.dmf.capabilities import DMFProfileContext
from klein.profiles.dmf.frames import dmf_payload_to_frames
from klein.profiles.dmf.validation import PayloadValidationError, validate_dmf_payload
from klein.substrate.api import Frame

DEFAULT_FRAME_DURATION_MS = 20
DEFAULT_VOLTAGE_V = 200.0


class PayloadKind(str, Enum):
    """DMF payload data formats from container.schema.json."""

    CHANNEL_LIST = "CHANNEL_LIST"
    FRAME_SEQUENCE = "FRAME_SEQUENCE"
    BITMAP_SEQUENCE = "BITMAP_SEQUENCE"


class PayloadEncoding(str, Enum):
    """Container payload encoding formats."""

    JSON = "JSON"
    BASE64_GZIP = "BASE64_GZIP"
    RLE = "RLE"


@dataclass
class ChannelEntry:
    """A single channel activation entry from CHANNEL_LIST payload."""

    t: int
    channel_id: int
    state: str
    voltage_v: float
    frequency_hz: float | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChannelEntry:
        return cls(
            t=data["t"],
            channel_id=data["channel_id"],
            state=data["state"],
            voltage_v=data["voltage_v"],
            frequency_hz=data.get("frequency_hz"),
        )


@dataclass
class FrameEntry:
    """A single frame entry from FRAME_SEQUENCE payload."""

    t: int
    format: str
    data: Any

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FrameEntry:
        return cls(t=data["t"], format=data["format"], data=data["data"])


@dataclass
class FrameSequence:
    """A sequence of frames generated from DMF payload parsing."""

    frames: list[Frame]
    source_kind: PayloadKind


class PayloadParser:
    """Validates and converts DMF/EWOD v1 payloads to substrate frames."""

    def __init__(
        self,
        context: DMFProfileContext | None = None,
        default_duration_ms: int = DEFAULT_FRAME_DURATION_MS,
        max_channels: int | None = None,
        grid_width: int | None = None,
        grid_height: int | None = None,
        voltage_min_v: float | None = None,
        voltage_max_v: float | None = None,
        frequency_min_hz: float | None = None,
        frequency_max_hz: float | None = None,
    ):
        base = context or DMFProfileContext()
        if any(
            value is not None
            for value in (
                max_channels,
                grid_width,
                grid_height,
                voltage_min_v,
                voltage_max_v,
                frequency_min_hz,
                frequency_max_hz,
            )
        ):
            base = DMFProfileContext(
                max_channels=max_channels if max_channels is not None else base.max_channels,
                grid_width=grid_width if grid_width is not None else base.grid_width,
                grid_height=grid_height if grid_height is not None else base.grid_height,
                voltage_min_v=voltage_min_v if voltage_min_v is not None else base.voltage_min_v,
                voltage_max_v=voltage_max_v if voltage_max_v is not None else base.voltage_max_v,
                frequency_min_hz=frequency_min_hz if frequency_min_hz is not None else base.frequency_min_hz,
                frequency_max_hz=frequency_max_hz if frequency_max_hz is not None else base.frequency_max_hz,
                addressing_mode=base.addressing_mode,
            )
        self._context = base
        self._default_duration_ms = default_duration_ms
        self._seq_counter = 0

    @property
    def context(self) -> DMFProfileContext:
        return self._context

    def reset(self) -> None:
        self._seq_counter = 0

    def validate_container_payload(self, payload: dict[str, Any]) -> list[PayloadValidationError]:
        return validate_dmf_payload(payload, self._context)

    def parse_container_payload(self, payload: dict[str, Any]) -> FrameSequence:
        kind = PayloadKind(payload.get("kind", PayloadKind.CHANNEL_LIST.value))
        data = self._decode_payload_data(payload)
        frames = dmf_payload_to_frames(
            kind=kind,
            data=data,
            context=self._context,
            next_seq=self._next_seq,
            default_duration_ms=self._default_duration_ms,
        )
        return FrameSequence(frames=frames, source_kind=kind)

    def _next_seq(self) -> int:
        self._seq_counter += 1
        return self._seq_counter

    def _decode_payload_data(self, payload: dict[str, Any]) -> Any:
        encoding = PayloadEncoding(payload.get("encoding", PayloadEncoding.JSON.value))
        data = payload.get("data", [])
        if encoding == PayloadEncoding.JSON:
            return data
        if encoding == PayloadEncoding.BASE64_GZIP:
            if not isinstance(data, str):
                raise ValueError(ErrorCode.PAYLOAD_MALFORMED.value)
            decoded = base64.b64decode(data, validate=True)
            return json.loads(gzip.decompress(decoded))
        raise ValueError(ErrorCode.PAYLOAD_UNSUPPORTED_FRAME_FORMAT.value)

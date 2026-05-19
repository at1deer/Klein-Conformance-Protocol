"""Capability/topology context for the DMF/EWOD profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from klein.common.errors import ErrorCode
from klein.substrate.api import (
    AddressingMode,
    CapabilityProfile,
    ElectrodeTopology,
    SubstrateDriver,
)

DEFAULT_MAX_CHANNELS = 128
DEFAULT_GRID_WIDTH = 16
DEFAULT_GRID_HEIGHT = 8
DEFAULT_VOLTAGE_MIN_V = 0.0
DEFAULT_VOLTAGE_MAX_V = 300.0
DEFAULT_FREQUENCY_MIN_HZ = 1.0
DEFAULT_FREQUENCY_MAX_HZ = 50_000.0


@dataclass(frozen=True)
class DMFProfileContext:
    """Declared substrate bounds used by the DMF profile validator."""

    max_channels: int = DEFAULT_MAX_CHANNELS
    grid_width: int = DEFAULT_GRID_WIDTH
    grid_height: int = DEFAULT_GRID_HEIGHT
    voltage_min_v: float = DEFAULT_VOLTAGE_MIN_V
    voltage_max_v: float = DEFAULT_VOLTAGE_MAX_V
    frequency_min_hz: float = DEFAULT_FREQUENCY_MIN_HZ
    frequency_max_hz: float = DEFAULT_FREQUENCY_MAX_HZ
    addressing_mode: str = AddressingMode.DIRECT.value


@dataclass(frozen=True)
class DmfCapabilitiesValidationResult:
    """Validation result for a DMF/EWOD capability block."""

    ok: bool
    context: DMFProfileContext | None = None
    error_code: ErrorCode | None = None
    message: str | None = None
    detail: dict[str, Any] | None = None


SUPPORTED_PAYLOAD_KINDS = {"CHANNEL_LIST", "FRAME_SEQUENCE", "BITMAP_SEQUENCE"}
SUPPORTED_FRAME_FORMATS = {"sparse", "bitmap", "delta_tiles"}
UNSUPPORTED_FRAME_FORMATS = {"rle"}


def build_dmf_profile_context(
    capabilities: dict[str, Any],
    topology: Any | None = None,
) -> DMFProfileContext:
    """Build a DMF profile context from a capability declaration block."""
    del topology
    addressing = capabilities["addressing"]
    electrical = capabilities["electrical"]
    return DMFProfileContext(
        max_channels=int(addressing["max_channels"]),
        grid_width=int(addressing["grid_width"]),
        grid_height=int(addressing["grid_height"]),
        voltage_min_v=float(electrical["voltage_min_v"]),
        voltage_max_v=float(electrical["voltage_max_v"]),
        frequency_min_hz=float(electrical["frequency_min_hz"]),
        frequency_max_hz=float(electrical["frequency_max_hz"]),
        addressing_mode=str(addressing["mode"]),
    )


def validate_dmf_capabilities(data: Any) -> DmfCapabilitiesValidationResult:
    """Validate the DMF capability block used by backend capability declarations."""
    if not isinstance(data, dict):
        return _capability_error("DMF capability block must be an object")
    for section in ("addressing", "electrical", "payloads", "sensing", "recovery"):
        if not isinstance(data.get(section), dict):
            return _capability_error(f"DMF capabilities missing {section}")
    addressing = data["addressing"]
    for field in ("max_channels", "grid_width", "grid_height"):
        value = addressing.get(field)
        if type(value) is not int or value <= 0:
            return _capability_error(f"DMF addressing.{field} must be a positive integer", {field: value})
    if addressing.get("mode") not in {"channel", "direct"}:
        return _capability_error("DMF addressing.mode is unsupported", {"mode": addressing.get("mode")})
    electrical = data["electrical"]
    for field in ("voltage_min_v", "voltage_max_v", "frequency_min_hz", "frequency_max_hz"):
        if isinstance(electrical.get(field), bool) or not isinstance(electrical.get(field), (int, float)):
            return _capability_error(f"DMF electrical.{field} must be numeric", {field: electrical.get(field)})
    if float(electrical["voltage_min_v"]) > float(electrical["voltage_max_v"]):
        return _capability_error("DMF voltage_min_v must be <= voltage_max_v")
    if float(electrical["frequency_min_hz"]) > float(electrical["frequency_max_hz"]):
        return _capability_error("DMF frequency_min_hz must be <= frequency_max_hz")

    payloads = data["payloads"]
    supported_kinds = _string_set(payloads.get("supported_payload_kinds"))
    supported_formats = _string_set(payloads.get("supported_frame_formats"))
    unsupported_formats = _string_set(payloads.get("unsupported_frame_formats"))
    if not supported_kinds or not supported_kinds <= SUPPORTED_PAYLOAD_KINDS:
        return _capability_error("DMF supported_payload_kinds contains unsupported kind", {"supported_payload_kinds": sorted(supported_kinds)})
    if not supported_formats or not supported_formats <= SUPPORTED_FRAME_FORMATS:
        return _capability_error("DMF supported_frame_formats contains unsupported format", {"supported_frame_formats": sorted(supported_formats)})
    if supported_formats & unsupported_formats:
        return _capability_error("DMF frame format cannot be both supported and unsupported")
    if "rle" in supported_formats:
        return _capability_error("DMF rle frame format is unsupported in alpha")

    sensing = data["sensing"]
    if sensing.get("supports_physical_sensor_attestation") is not False:
        return _capability_error("DMF alpha must not claim physical sensor attestation")
    recovery = data["recovery"]
    if recovery.get("supports_closed_loop_recovery") is not False:
        return _capability_error("DMF alpha must not claim closed-loop recovery")
    return DmfCapabilitiesValidationResult(ok=True, context=build_dmf_profile_context(data))


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in value if isinstance(item, str)}


def _capability_error(
    message: str,
    detail: dict[str, Any] | None = None,
) -> DmfCapabilitiesValidationResult:
    return DmfCapabilitiesValidationResult(
        ok=False,
        error_code=ErrorCode.DMF_CAPABILITIES_INVALID,
        message=message,
        detail=detail or {},
    )


def context_from_substrate(substrate: SubstrateDriver) -> DMFProfileContext:
    """Build a DMF profile context from a connected substrate driver."""
    try:
        capabilities = substrate.get_capabilities()
        topology = substrate.get_topology()
    except Exception:
        return DMFProfileContext()
    return context_from_capabilities(capabilities, topology)


def context_from_capabilities(
    capabilities: CapabilityProfile,
    topology: ElectrodeTopology | None = None,
) -> DMFProfileContext:
    """Build a DMF profile context from declared capabilities and topology."""
    grid_width, grid_height = _grid_size_from_topology(topology, capabilities.max_channels)
    frequency_range = capabilities.ac_frequency_range
    addressing = capabilities.addressing
    if hasattr(addressing, "value"):
        addressing_mode = addressing.value
    else:
        addressing_mode = str(addressing)
    return DMFProfileContext(
        max_channels=capabilities.max_channels,
        grid_width=grid_width,
        grid_height=grid_height,
        voltage_min_v=capabilities.voltage_range.v_min,
        voltage_max_v=capabilities.voltage_range.v_max,
        frequency_min_hz=(
            frequency_range.hz_min
            if frequency_range is not None and frequency_range.hz_min is not None
            else DEFAULT_FREQUENCY_MIN_HZ
        ),
        frequency_max_hz=(
            frequency_range.hz_max
            if frequency_range is not None and frequency_range.hz_max is not None
            else DEFAULT_FREQUENCY_MAX_HZ
        ),
        addressing_mode=addressing_mode,
    )


def _grid_size_from_topology(
    topology: ElectrodeTopology | None,
    max_channels: int,
) -> tuple[int, int]:
    if topology is None:
        return max_channels, 1

    coordinates: list[tuple[int, int]] = []
    for electrode in topology.electrodes:
        x = _coordinate_to_int(electrode.x)
        y = _coordinate_to_int(electrode.y)
        if x is not None and y is not None:
            coordinates.append((x, y))
    if coordinates:
        width = max(x for x, _ in coordinates) + 1
        height = max(y for _, y in coordinates) + 1
        return max(width, 1), max(height, 1)

    count = len(topology.electrodes) or max_channels
    return count, 1


def _coordinate_to_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


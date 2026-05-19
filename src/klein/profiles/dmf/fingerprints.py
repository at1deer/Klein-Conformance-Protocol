"""Canonical DMF profile capability and topology fingerprints."""

from __future__ import annotations

from typing import Any

from klein.common.hashing import HashResult, hash_json_value
from klein.substrate.api import CapabilityProfile, ElectrodeTopology, SubstrateDriver


def _enum_value(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


def capabilities_payload(capabilities: CapabilityProfile) -> dict[str, Any]:
    """Return the canonical JSON payload for declared substrate capabilities."""
    frequency = capabilities.ac_frequency_range
    return {
        "device_vendor": capabilities.device_vendor,
        "device_model": capabilities.device_model,
        "firmware": capabilities.firmware,
        "max_channels": capabilities.max_channels,
        "addressing": _enum_value(capabilities.addressing),
        "supports_groups": capabilities.supports_groups,
        "waveforms": [_enum_value(waveform) for waveform in capabilities.waveforms],
        "voltage_range": {
            "v_min": capabilities.voltage_range.v_min,
            "v_max": capabilities.voltage_range.v_max,
        },
        "ac_frequency_range": (
            None
            if frequency is None
            else {
                "hz_min": frequency.hz_min,
                "hz_max": frequency.hz_max,
            }
        ),
        "timing": {
            "min_frame_ms": capabilities.timing.min_frame_ms,
            "typical_jitter_ms": capabilities.timing.typical_jitter_ms,
            "max_schedule_horizon_ms": capabilities.timing.max_schedule_horizon_ms,
        },
        "sensing": {
            "impedance": capabilities.sensing.impedance,
            "vision": capabilities.sensing.vision,
            "electrode_feedback": capabilities.sensing.electrode_feedback,
        },
        "safety_estop": capabilities.safety_estop,
        "safety_overcurrent_protection": capabilities.safety_overcurrent_protection,
    }


def topology_payload(topology: ElectrodeTopology) -> dict[str, Any]:
    """Return the canonical JSON payload for declared electrode topology."""
    return {
        "cartridge_id": topology.cartridge_id,
        "electrodes": [
            {
                "eid": electrode.eid,
                "label": electrode.label,
                "x": electrode.x,
                "y": electrode.y,
            }
            for electrode in sorted(topology.electrodes, key=lambda item: item.eid)
        ],
        "adjacency": {
            str(eid): list(neighbors)
            for eid, neighbors in sorted(topology.adjacency.items(), key=lambda item: item[0])
        },
    }


def hash_capabilities(capabilities: CapabilityProfile) -> HashResult:
    """Hash declared substrate capabilities with Klein canonical JSON v1."""
    return hash_json_value(capabilities_payload(capabilities))


def hash_topology(topology: ElectrodeTopology) -> HashResult:
    """Hash declared substrate topology with Klein canonical JSON v1."""
    return hash_json_value(topology_payload(topology))


def substrate_fingerprint_payload(
    capabilities: CapabilityProfile,
    topology: ElectrodeTopology,
) -> dict[str, Any]:
    """Return the canonical payload bound into a substrate fingerprint."""
    return {
        "capabilities": capabilities_payload(capabilities),
        "topology": topology_payload(topology),
    }


def hash_substrate_fingerprint(
    capabilities: CapabilityProfile,
    topology: ElectrodeTopology,
) -> HashResult:
    """Hash declared substrate capabilities and topology together."""
    return hash_json_value(substrate_fingerprint_payload(capabilities, topology))


def substrate_fingerprint_details(substrate: SubstrateDriver) -> dict[str, str]:
    """Return report fields binding execution to substrate declarations."""
    capabilities = substrate.get_capabilities()
    topology = substrate.get_topology()
    capabilities_hash = hash_capabilities(capabilities)
    topology_hash = hash_topology(topology)
    fingerprint = hash_substrate_fingerprint(capabilities, topology)
    return {
        "substrate_capabilities_hash": capabilities_hash.ref,
        "substrate_capabilities_canonicalization": capabilities_hash.canonicalization,
        "substrate_topology_hash": topology_hash.ref,
        "substrate_topology_canonicalization": topology_hash.canonicalization,
        "substrate_fingerprint": fingerprint.ref,
        "substrate_fingerprint_canonicalization": fingerprint.canonicalization,
    }

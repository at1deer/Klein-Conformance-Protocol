"""Protocol for HIL-ready backends."""

from __future__ import annotations

from typing import Any, Protocol

from klein.substrate.api import Ack, CapabilityProfile, ElectrodeTopology, Frame


class HilBackendProtocol(Protocol):
    """Interface future hardware backends must satisfy."""

    def connect(self) -> dict[str, Any]:
        ...

    def disconnect(self) -> dict[str, Any]:
        ...

    def get_capabilities(self) -> CapabilityProfile:
        ...

    def get_topology(self) -> ElectrodeTopology:
        ...

    def get_health(self) -> dict[str, Any]:
        ...

    def apply_frame(self, frame: Frame) -> Ack:
        ...

    def read_observation(self) -> dict[str, Any]:
        ...

    def emergency_stop(self) -> dict[str, Any]:
        ...

    def reset(self) -> dict[str, Any]:
        ...

    def export_raw_device_log(self) -> list[dict[str, Any]]:
        ...

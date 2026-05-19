"""OpenDrop/EWOD status helpers."""

from __future__ import annotations

from typing import Any

from klein.backends.dmf.opendrop.config import validate_opendrop_adapter_status

__all__ = ["validate_opendrop_adapter_status"]


def is_emergency_stopped(status: dict[str, Any]) -> bool:
    return bool(status.get("emergency_stopped"))

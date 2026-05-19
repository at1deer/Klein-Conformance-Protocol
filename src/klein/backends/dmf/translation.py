"""Runbook-to-DMF command translation for dry-run adapters."""

from __future__ import annotations

from typing import Any

from klein.substrate.api import Frame


def runbook_step_to_frame(step: dict[str, Any], *, seq: int, max_channels: int) -> Frame:
    """Translate a Runbook v1 planned step into a dry-run command frame."""
    details = step.get("expected_effect", {}).get("details", {})
    channels = details.get("active_channels") if isinstance(details, dict) else None
    if not isinstance(channels, list):
        # Runbook v1 intentionally abstracts payload details. Dry-run skeletons use a deterministic
        # placeholder channel so translation is traceable without rehydrating the original artifact.
        channels = [int(step.get("tick", seq - 1)) % max_channels]
    active = tuple(int(channel) for channel in channels if isinstance(channel, int) and 0 <= channel < max_channels)
    return Frame(
        seq=seq,
        active_electrodes=active,
        duration_ms=10,
        tags={"tick": step.get("tick", seq - 1), "runbook_step_id": step.get("step_id"), "operation": step.get("operation")},
    )


def raw_event(index: int, operation: str, status: str, tick: int, details: dict[str, Any], *, error_code: str | None = None) -> dict[str, Any]:
    event = {
        "raw_log_version": "klein.raw_device_log.v1",
        "event_index": index,
        "source_type": "mock_hardware",
        "operation": operation,
        "status": status,
        "tick": tick,
        "details": details,
    }
    if error_code is not None:
        event["error_code"] = error_code
    return event

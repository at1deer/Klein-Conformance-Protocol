"""Build and hash Klein Runbook v1 artifacts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from klein.artifacts import canonical_artifact_hash, detect_artifact_type
from klein.artifacts.validation import load_json_artifact
from klein.execution.validation import canonical_runbook_hash, validate_runbook


def build_runbook_from_artifact(
    artifact: dict[str, Any] | str | Path,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a deterministic current-alpha runbook from a supported artifact."""
    context = context or {}
    if isinstance(artifact, str | Path):
        artifact_data = load_json_artifact(artifact)
        artifact_hash = canonical_artifact_hash(artifact).ref
        artifact_type = detect_artifact_type(artifact)
    else:
        artifact_data = artifact
        artifact_hash = canonical_artifact_hash(artifact_data).ref
        artifact_type = detect_artifact_type(artifact_data)

    profile_id, profile_version, mode = _profile_mode(artifact_type, artifact_data, context)
    payload = _primary_payload(artifact_type, artifact_data)
    return {
        "runbook_version": "klein.runbook.v1",
        "runbook_id": context.get("runbook_id"),
        "source_artifact_hash": artifact_hash,
        "source_artifact_type": artifact_type,
        "profile": {"profile_id": profile_id, "profile_version": profile_version},
        "mode": mode,
        "substrate_fingerprint": context.get("substrate_fingerprint"),
        "timebase": "DEVICE_TICKS",
        "planned_steps": _planned_steps(payload),
        "metadata": dict(context.get("metadata") or {}),
    }


def _profile_mode(
    artifact_type: str,
    artifact: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str, str]:
    if artifact.get("kind") == "KLEIN_PROJECT":
        profile = artifact.get("profile", {})
        return profile.get("profile_id", "dmf"), profile.get("profile_version", "v1"), artifact.get("mode", "HARD")
    if artifact.get("kind") == "KLEIN_CONTAINER":
        profile = artifact.get("profile", {})
        return profile.get("profile_id", "dmf"), profile.get("profile_version", "v1"), artifact.get("mode", "HARD")
    if artifact_type == "container":
        runtime = artifact.get("manifest", {}).get("runtime", {})
        return "dmf", "v1", runtime.get("mode", "HARD")
    return (
        context.get("profile_id", "core"),
        context.get("profile_version", "v1"),
        context.get("mode", "HARD"),
    )


def _primary_payload(artifact_type: str, artifact: dict[str, Any]) -> dict[str, Any] | None:
    if artifact.get("kind") == "KLEIN_PROJECT":
        return artifact.get("payload") if isinstance(artifact.get("payload"), dict) else None
    if artifact.get("kind") == "KLEIN_CONTAINER":
        payloads = artifact.get("payloads")
        if isinstance(payloads, list) and payloads:
            payload = payloads[0]
            return {
                "kind": payload.get("payload_kind"),
                "encoding": payload.get("encoding"),
                "data": payload.get("data"),
            }
    if artifact_type == "container":
        return artifact.get("payload") if isinstance(artifact.get("payload"), dict) else None
    return None


def _planned_steps(payload: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not payload:
        return []
    kind = payload.get("kind")
    data = payload.get("data") if isinstance(payload.get("data"), list) else []
    ticks = _payload_ticks(kind, data)
    operation = _operation_for_kind(kind)
    return [
        {
            "step_id": f"step-{index + 1:04d}",
            "tick": tick,
            "operation": operation,
            "payload_ref": "payload-001",
            "frame_ref": f"frame-{index + 1:04d}",
            "expected_effect": {"type": "simulated", "details": {}},
        }
        for index, tick in enumerate(ticks)
    ]


def _payload_ticks(kind: Any, data: list[Any]) -> list[int]:
    if kind == "CHANNEL_LIST":
        return sorted({int(entry.get("t", 0)) for entry in data if isinstance(entry, dict)})
    if kind == "FRAME_SEQUENCE":
        return [int(entry.get("t", index)) for index, entry in enumerate(data) if isinstance(entry, dict)]
    if kind == "BITMAP_SEQUENCE":
        return list(range(len(data)))
    return []


def _operation_for_kind(kind: Any) -> str:
    if kind == "CHANNEL_LIST":
        return "DMF_SET_CHANNELS"
    if kind == "BITMAP_SEQUENCE":
        return "DMF_APPLY_BITMAP"
    return "DMF_APPLY_FRAME"


__all__ = ["build_runbook_from_artifact", "canonical_runbook_hash", "validate_runbook"]

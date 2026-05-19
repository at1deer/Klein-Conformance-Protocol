"""Observation Snapshot v1 validation and comparison."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.common.hashing import HashResult, hash_json_artifact, hash_json_value, parse_ijson

OBSERVATION_SNAPSHOT_VERSION = "klein.observation_snapshot.v1"
OBSERVATION_POLICY_VERSION = "klein.observation_policy.v1"
TIMEBASE = "DEVICE_TICKS"


class ObservationError(ValueError):
    """Structured observation validation failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class ObservationValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    observation_count: int = 0


def load_observation_json(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ObservationError("OBSERVATION_SCHEMA_INVALID", "observation artifact root must be an object")
    return data


def canonical_observation_hash(data_or_path: dict[str, Any] | str | Path) -> HashResult:
    if isinstance(data_or_path, str | Path):
        return hash_json_artifact(Path(data_or_path))
    return hash_json_value(data_or_path)


def default_observation_policy() -> dict[str, Any]:
    return {
        "observation_policy_version": OBSERVATION_POLICY_VERSION,
        "policy_id": "simulated-dmf-alpha",
        "required_for_recovery_success": True,
        "allowed_sources": ["simulator"],
        "allowed_observation_models": ["simulated"],
        "requires_trace_alignment": True,
        "requires_runbook_alignment": False,
        "requires_attestation": False,
    }


def validate_observation_policy(policy: dict[str, Any]) -> ObservationValidationResult:
    if policy.get("observation_policy_version") != OBSERVATION_POLICY_VERSION:
        return _failure("OBSERVATION_POLICY_SCHEMA_INVALID", "unsupported observation_policy_version")
    allowed_sources = policy.get("allowed_sources")
    if not isinstance(allowed_sources, list) or not allowed_sources:
        return _failure("OBSERVATION_POLICY_SCHEMA_INVALID", "allowed_sources must be a non-empty list")
    if any(source not in {"simulator", "hardware_sensor"} for source in allowed_sources):
        return _failure("OBSERVATION_SOURCE_UNSUPPORTED", "observation policy names an unsupported source")
    if "hardware_sensor" in allowed_sources:
        return _failure("OBSERVATION_SOURCE_UNSUPPORTED", "hardware_sensor observations are not CURRENT_ALPHA")
    models = policy.get("allowed_observation_models")
    if not isinstance(models, list) or not models:
        return _failure("OBSERVATION_POLICY_SCHEMA_INVALID", "allowed_observation_models must be a non-empty list")
    if any(model != "simulated" for model in models):
        return _failure("OBSERVATION_POLICY_INVALID", "only simulated observation_model is supported in alpha")
    if policy.get("requires_attestation"):
        return _failure("OBSERVATION_ATTESTATION_UNSUPPORTED", "attestation is not supported for simulator observations")
    return ObservationValidationResult(ok=True)


def validate_observation_snapshot(
    snapshot: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> ObservationValidationResult:
    if snapshot.get("observation_version") != OBSERVATION_SNAPSHOT_VERSION:
        return _failure("OBSERVATION_SCHEMA_INVALID", "unsupported observation_version")
    for field in ("observation_id", "run_id", "timebase", "tick", "profile", "source", "observation_model", "confidence", "state", "metadata"):
        if field not in snapshot:
            return _failure("OBSERVATION_SCHEMA_INVALID", f"observation missing required field {field}")
    if snapshot.get("timebase") != TIMEBASE:
        return _failure("OBSERVATION_SCHEMA_INVALID", "observation timebase is invalid")
    confidence = snapshot.get("confidence")
    if not isinstance(confidence, int | float) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
        return _failure("OBSERVATION_CONFIDENCE_INVALID", "observation confidence must be in [0, 1]")
    source = snapshot.get("source")
    if not isinstance(source, dict):
        return _failure("OBSERVATION_SCHEMA_INVALID", "observation source must be an object")
    if source.get("source_type") != "simulator":
        return _failure("OBSERVATION_SOURCE_UNSUPPORTED", "only simulator observations are CURRENT_ALPHA")
    if source.get("attestation") is not None:
        return _failure("OBSERVATION_ATTESTATION_UNSUPPORTED", "simulator observations must not carry attestation")
    if snapshot.get("observation_model") != "simulated":
        return _failure("OBSERVATION_SOURCE_UNSUPPORTED", "only simulated observation_model is supported")
    return validate_dmf_observation_state(snapshot.get("state", {}).get("dmf", {}), context=context)


def validate_dmf_observation_state(
    state: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> ObservationValidationResult:
    if not isinstance(state, dict):
        return _failure("OBSERVATION_DMF_STATE_INVALID", "dmf state must be an object")
    active_channels = state.get("active_channels")
    active_tiles = state.get("active_tiles")
    if not isinstance(active_channels, list) or not all(isinstance(channel, int) and channel >= 0 for channel in active_channels):
        return _failure("OBSERVATION_DMF_STATE_INVALID", "active_channels must be non-negative integers")
    if not isinstance(active_tiles, list):
        return _failure("OBSERVATION_DMF_STATE_INVALID", "active_tiles must be a list")
    for tile in active_tiles:
        if (
            not isinstance(tile, list | tuple)
            or len(tile) != 2
            or not all(isinstance(coord, int) and coord >= 0 for coord in tile)
        ):
            return _failure("OBSERVATION_DMF_STATE_INVALID", "active_tiles must contain [x, y] integer pairs")
    if context:
        max_channels = context.get("max_channels")
        if isinstance(max_channels, int) and any(channel >= max_channels for channel in active_channels):
            return _failure("OBSERVATION_DMF_STATE_INVALID", "active channel is outside substrate context")
        grid_width = context.get("grid_width")
        grid_height = context.get("grid_height")
        if isinstance(grid_width, int) and isinstance(grid_height, int):
            for x, y in active_tiles:
                if x >= grid_width or y >= grid_height:
                    return _failure("OBSERVATION_DMF_STATE_INVALID", "active tile is outside grid context")
    return ObservationValidationResult(ok=True)


def compare_observation_to_trace(
    observation: dict[str, Any],
    trace: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> ObservationValidationResult:
    validation = validate_observation_snapshot(observation, context=context)
    if not validation.ok:
        return validation
    trace_step_id = observation.get("trace_step_id")
    trace_ids = {step.get("step_id") for step in trace.get("trace_steps", [])}
    if trace_step_id not in trace_ids:
        return _failure("OBSERVATION_TRACE_MISMATCH", "observation trace_step_id is not present in trace")
    return ObservationValidationResult(ok=True, observation_count=1)


def compare_observation_to_runbook(
    observation: dict[str, Any],
    runbook: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> ObservationValidationResult:
    validation = validate_observation_snapshot(observation, context=context)
    if not validation.ok:
        return validation
    runbook_step_id = observation.get("runbook_step_id")
    runbook_ids = {step.get("step_id") for step in runbook.get("planned_steps", [])}
    if runbook_step_id not in runbook_ids:
        return _failure("OBSERVATION_RUNBOOK_MISMATCH", "observation runbook_step_id is not present in runbook")
    return ObservationValidationResult(ok=True, observation_count=1)


def validate_observation_contract(
    observations: list[dict[str, Any]],
    trace: dict[str, Any],
    runbook: dict[str, Any],
    policy: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    recovery_success: bool = False,
) -> ObservationValidationResult:
    policy_result = validate_observation_policy(policy)
    if not policy_result.ok:
        return policy_result
    if recovery_success and policy.get("required_for_recovery_success") and not observations:
        return _failure("OBSERVATION_REQUIRED_MISSING", "recovery success requires observation evidence")
    for observation in observations:
        validation = validate_observation_snapshot(observation, context=context)
        if not validation.ok:
            return validation
        if observation.get("source", {}).get("source_type") not in set(policy.get("allowed_sources", [])):
            return _failure("OBSERVATION_SOURCE_UNSUPPORTED", "observation source is not allowed by policy")
        if observation.get("observation_model") not in set(policy.get("allowed_observation_models", [])):
            return _failure("OBSERVATION_POLICY_INVALID", "observation model is not allowed by policy")
        if policy.get("requires_trace_alignment"):
            trace_result = compare_observation_to_trace(observation, trace, context=context)
            if not trace_result.ok:
                return trace_result
        if policy.get("requires_runbook_alignment"):
            runbook_result = compare_observation_to_runbook(observation, runbook, context=context)
            if not runbook_result.ok:
                return runbook_result
    return ObservationValidationResult(ok=True, observation_count=len(observations))


def build_dmf_simulated_observation(
    *,
    observation_id: str,
    run_id: str,
    tick: int,
    runbook_step_id: str,
    trace_step_id: str,
    active_channels: list[int],
    profile_version: str = "v1",
    source_id: str = "full_simulator",
    source_version: str = "1.0.0a0",
    grid_width: int = 16,
) -> dict[str, Any]:
    return {
        "observation_version": OBSERVATION_SNAPSHOT_VERSION,
        "observation_id": observation_id,
        "run_id": run_id,
        "timebase": TIMEBASE,
        "tick": tick,
        "profile": {"profile_id": "dmf", "profile_version": profile_version},
        "source": {
            "source_type": "simulator",
            "source_id": source_id,
            "source_version": source_version,
            "attestation": None,
        },
        "observation_model": "simulated",
        "confidence": 1.0,
        "runbook_step_id": runbook_step_id,
        "trace_step_id": trace_step_id,
        "state": {"dmf": {"active_channels": active_channels, "active_tiles": _channels_to_tiles(active_channels, grid_width)}},
        "metadata": {},
    }


def build_dmf_simulated_observations_from_events(
    events: list[dict[str, Any]],
    trace: dict[str, Any],
    *,
    run_id: str,
    profile_version: str = "v1",
    source_id: str = "full_simulator",
    source_version: str = "1.0.0a0",
    grid_width: int = 16,
) -> list[dict[str, Any]]:
    observations = []
    applied_events = [
        event for event in events
        if event.get("kind") == "DEVICE_EVENT" and event.get("code") == "FRAME_APPLIED"
    ]
    applied_trace_steps = [step for step in trace.get("trace_steps", []) if step.get("status") == "APPLIED"]
    for index, event in enumerate(applied_events, start=1):
        trace_step = applied_trace_steps[min(index - 1, len(applied_trace_steps) - 1)] if applied_trace_steps else None
        if trace_step is None:
            continue
        active_channels = list(event.get("detail", {}).get("electrodes", []))
        observations.append(
            build_dmf_simulated_observation(
                observation_id=f"obs-{index:04d}",
                run_id=run_id,
                tick=int(event.get("t", 0)),
                runbook_step_id=str(trace_step.get("runbook_step_id")),
                trace_step_id=str(trace_step.get("step_id")),
                active_channels=active_channels,
                profile_version=profile_version,
                source_id=source_id,
                source_version=source_version,
                grid_width=grid_width,
            )
        )
    return observations


def _channels_to_tiles(channels: list[int], grid_width: int) -> list[list[int]]:
    return [[channel % grid_width, channel // grid_width] for channel in channels]


def _failure(error_code: str, message: str) -> ObservationValidationResult:
    return ObservationValidationResult(ok=False, error_code=error_code, message=message)

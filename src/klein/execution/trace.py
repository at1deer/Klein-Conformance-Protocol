"""Build, hash, and compare Klein Execution Trace v1 artifacts."""

from __future__ import annotations

from typing import Any

from klein.execution.validation import (
    TraceComparisonResult,
    canonical_trace_hash,
    compare_trace_to_runbook,
    validate_execution_trace,
)


def build_trace_from_runbook(
    runbook: dict[str, Any],
    *,
    run_id: str,
    backend_id: str,
    backend_version: str,
    success: bool = True,
    error_code: str | None = None,
) -> dict[str, Any]:
    """Build a current-alpha simulator trace from a runbook."""
    runbook_hash = _runbook_hash_ref(runbook)
    trace_steps = []
    for step in runbook.get("planned_steps", []):
        failed = not success and error_code is not None
        trace_steps.append(
            {
                "step_id": step["step_id"],
                "runbook_step_id": step["step_id"],
                "tick": step["tick"],
                "operation": step["operation"],
                "issued": True,
                "applied": not failed,
                "status": "FAILED" if failed else "APPLIED",
                "error_code": error_code if failed else None,
                "details": {},
            }
        )
        if failed:
            break
    return {
        "trace_version": "klein.execution_trace.v1",
        "trace_id": None,
        "run_id": run_id,
        "runbook_hash": runbook_hash,
        "artifact_hash": runbook["source_artifact_hash"],
        "profile": dict(runbook["profile"]),
        "backend": {"backend_id": backend_id, "backend_version": backend_version},
        "timebase": "DEVICE_TICKS",
        "trace_steps": trace_steps,
        "metadata": {},
    }


def build_trace_from_execution_result(
    runbook: dict[str, Any],
    *,
    run_id: str,
    backend_id: str,
    backend_version: str,
    execution_success: bool,
    error_code: str | None,
) -> dict[str, Any]:
    return build_trace_from_runbook(
        runbook,
        run_id=run_id,
        backend_id=backend_id,
        backend_version=backend_version,
        success=execution_success,
        error_code=error_code,
    )


def build_trace_from_hail_events(
    runbook: dict[str, Any],
    events: list[dict[str, Any]],
    *,
    run_id: str,
    backend_id: str,
    backend_version: str,
    execution_success: bool,
    error_code: str | None,
) -> dict[str, Any]:
    """Build a trace from HAIL evidence, including the narrow ECRP retry-success shape."""
    if _has_successful_ecrp_retry(events):
        return _build_successful_retry_trace(
            runbook,
            run_id=run_id,
            backend_id=backend_id,
            backend_version=backend_version,
        )
    return build_trace_from_execution_result(
        runbook,
        run_id=run_id,
        backend_id=backend_id,
        backend_version=backend_version,
        execution_success=execution_success,
        error_code=error_code,
    )


def _runbook_hash_ref(runbook: dict[str, Any]) -> str:
    from klein.execution.validation import canonical_runbook_hash

    return canonical_runbook_hash(runbook).ref


def _has_successful_ecrp_retry(events: list[dict[str, Any]]) -> bool:
    return any(
        event.get("kind") == "ECRP_ATTEMPT"
        and event.get("outcome") == "SUCCESS"
        and event.get("strategy") == "NUDGE_PULSE"
        for event in events
    )


def _build_successful_retry_trace(
    runbook: dict[str, Any],
    *,
    run_id: str,
    backend_id: str,
    backend_version: str,
) -> dict[str, Any]:
    runbook_hash = _runbook_hash_ref(runbook)
    step = runbook.get("planned_steps", [])[0]
    trace_steps = [
        {
            "step_id": f"{step['step_id']}-original",
            "runbook_step_id": step["step_id"],
            "tick": step["tick"],
            "operation": step["operation"],
            "issued": True,
            "applied": False,
            "status": "FAILED",
            "error_code": "FRAME_FAILED",
            "details": {"recovery_parent_step_id": step["step_id"]},
        },
        {
            "step_id": f"{step['step_id']}-recovery-001",
            "runbook_step_id": step["step_id"],
            "tick": step["tick"],
            "operation": step["operation"],
            "issued": True,
            "applied": True,
            "status": "APPLIED",
            "error_code": None,
            "details": {
                "recovery_attempt_id": "attempt-001",
                "recovery_parent_step_id": step["step_id"],
                "recovery_strategy": "NUDGE_PULSE",
                "recovery_status": "issued",
            },
        },
        {
            "step_id": f"{step['step_id']}-retry-001",
            "runbook_step_id": step["step_id"],
            "tick": step["tick"],
            "operation": step["operation"],
            "issued": True,
            "applied": True,
            "status": "APPLIED",
            "error_code": None,
            "details": {
                "recovery_attempt_id": "attempt-001",
                "recovery_parent_step_id": step["step_id"],
                "recovery_strategy": "NUDGE_PULSE",
                "recovery_status": "success",
                "retry_of_step_id": step["step_id"],
            },
        },
    ]
    return {
        "trace_version": "klein.execution_trace.v1",
        "trace_id": None,
        "run_id": run_id,
        "runbook_hash": runbook_hash,
        "artifact_hash": runbook["source_artifact_hash"],
        "profile": dict(runbook["profile"]),
        "backend": {"backend_id": backend_id, "backend_version": backend_version},
        "timebase": "DEVICE_TICKS",
        "trace_steps": trace_steps,
        "metadata": {"ecrp_recovery_status": "success"},
    }


__all__ = [
    "TraceComparisonResult",
    "build_trace_from_execution_result",
    "build_trace_from_hail_events",
    "build_trace_from_runbook",
    "canonical_trace_hash",
    "compare_trace_to_runbook",
    "validate_execution_trace",
]

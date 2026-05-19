"""Runbook v1 and Execution Trace v1 validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.common.hashing import HashResult, hash_json_artifact, hash_json_value, parse_ijson

RUNBOOK_VERSION = "klein.runbook.v1"
TRACE_VERSION = "klein.execution_trace.v1"
TIMEBASE = "DEVICE_TICKS"
OPERATIONS = {"DMF_SET_CHANNELS", "DMF_APPLY_FRAME", "DMF_APPLY_BITMAP"}
MODES = {"HARD", "ENVELOPE", "DIAGNOSTIC"}
TRACE_STATUSES = {"APPLIED", "SKIPPED", "FAILED"}


class ExecutionArtifactError(ValueError):
    """Structured runbook/trace validation error."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None


@dataclass(frozen=True)
class TraceComparisonResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    matched_steps: int = 0
    runbook_steps: int = 0
    trace_steps: int = 0


def load_json(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ExecutionArtifactError("RUNBOOK_INVALID", "execution artifact root must be a JSON object")
    return data


def canonical_runbook_hash(data_or_path: dict[str, Any] | str | Path) -> HashResult:
    if isinstance(data_or_path, str | Path):
        return hash_json_artifact(Path(data_or_path))
    return hash_json_value(data_or_path)


def canonical_trace_hash(data_or_path: dict[str, Any] | str | Path) -> HashResult:
    if isinstance(data_or_path, str | Path):
        return hash_json_artifact(Path(data_or_path))
    return hash_json_value(data_or_path)


def validate_runbook(data: dict[str, Any]) -> ValidationResult:
    if data.get("runbook_version") != RUNBOOK_VERSION:
        return _failure("RUNBOOK_SCHEMA_INVALID", "unsupported runbook_version")
    for field in ("source_artifact_hash", "source_artifact_type", "profile", "mode", "substrate_fingerprint", "timebase", "planned_steps"):
        if field not in data:
            return _failure("RUNBOOK_SCHEMA_INVALID", f"runbook missing required field {field}")
    if data["source_artifact_type"] not in {"project", "container"}:
        return _failure("RUNBOOK_ARTIFACT_MISMATCH", "runbook source_artifact_type is unsupported")
    if data["mode"] not in MODES or data["timebase"] != TIMEBASE:
        return _failure("RUNBOOK_SCHEMA_INVALID", "runbook mode/timebase is invalid")
    profile = data["profile"]
    if not isinstance(profile, dict) or not profile.get("profile_id") or not profile.get("profile_version"):
        return _failure("RUNBOOK_PROFILE_MISMATCH", "runbook profile is missing")
    steps = data["planned_steps"]
    if not isinstance(steps, list):
        return _failure("RUNBOOK_SCHEMA_INVALID", "planned_steps must be a list")
    previous: tuple[int, str] | None = None
    for step in steps:
        if not isinstance(step, dict):
            return _failure("RUNBOOK_SCHEMA_INVALID", "planned step must be an object")
        result = _validate_step_common(step, "RUNBOOK_SCHEMA_INVALID")
        if not result.ok:
            return result
        current = (int(step["tick"]), str(step["step_id"]))
        if previous is not None and current < previous:
            return _failure("TRACE_STEP_ORDER_INVALID", "runbook planned_steps are not sorted")
        previous = current
    return ValidationResult(ok=True)


def validate_execution_trace(data: dict[str, Any]) -> ValidationResult:
    if data.get("trace_version") != TRACE_VERSION:
        return _failure("TRACE_SCHEMA_INVALID", "unsupported trace_version")
    for field in ("run_id", "runbook_hash", "artifact_hash", "profile", "backend", "timebase", "trace_steps"):
        if field not in data:
            return _failure("TRACE_SCHEMA_INVALID", f"trace missing required field {field}")
    if data["timebase"] != TIMEBASE:
        return _failure("TRACE_SCHEMA_INVALID", "trace timebase is invalid")
    steps = data["trace_steps"]
    if not isinstance(steps, list):
        return _failure("TRACE_SCHEMA_INVALID", "trace_steps must be a list")
    previous: tuple[int, str] | None = None
    for step in steps:
        if not isinstance(step, dict):
            return _failure("TRACE_SCHEMA_INVALID", "trace step must be an object")
        result = _validate_step_common(step, "TRACE_SCHEMA_INVALID")
        if not result.ok:
            return result
        if step.get("status") not in TRACE_STATUSES:
            return _failure("TRACE_STATUS_INVALID", "trace step status is invalid")
        if step["status"] == "FAILED" and (step.get("applied") is not False or not step.get("error_code")):
            return _failure("TRACE_STATUS_INVALID", "failed trace step must be unapplied with error_code")
        if step["status"] == "APPLIED" and step.get("applied") is not True:
            return _failure("TRACE_STATUS_INVALID", "applied trace step must set applied=true")
        current = (int(step["tick"]), str(step["step_id"]))
        if previous is not None and current < previous:
            return _failure("TRACE_STEP_ORDER_INVALID", "trace_steps are not sorted")
        previous = current
    return ValidationResult(ok=True)


def compare_trace_to_runbook(trace: dict[str, Any], runbook: dict[str, Any]) -> TraceComparisonResult:
    trace_validation = validate_execution_trace(trace)
    if not trace_validation.ok:
        return TraceComparisonResult(False, trace_validation.error_code, trace_validation.message)
    runbook_validation = validate_runbook(runbook)
    if not runbook_validation.ok:
        return TraceComparisonResult(False, runbook_validation.error_code, runbook_validation.message)
    runbook_steps = {step["step_id"]: step for step in runbook["planned_steps"]}
    matched = 0
    for trace_step in trace["trace_steps"]:
        planned = runbook_steps.get(trace_step["runbook_step_id"])
        if planned is None:
            return TraceComparisonResult(
                False,
                "TRACE_STEP_MISSING",
                f"trace references missing runbook step {trace_step['runbook_step_id']}",
                matched,
                len(runbook_steps),
                len(trace["trace_steps"]),
            )
        if planned["tick"] != trace_step["tick"] or planned["operation"] != trace_step["operation"]:
            return TraceComparisonResult(
                False,
                "TRACE_RUNBOOK_MISMATCH",
                f"trace step {trace_step['step_id']} differs from runbook step {planned['step_id']}",
                matched,
                len(runbook_steps),
                len(trace["trace_steps"]),
            )
        matched += 1
    if matched != len(runbook_steps):
        return TraceComparisonResult(
            False,
            "TRACE_STEP_MISSING",
            "trace does not cover every runbook step",
            matched,
            len(runbook_steps),
            len(trace["trace_steps"]),
        )
    return TraceComparisonResult(True, matched_steps=matched, runbook_steps=len(runbook_steps), trace_steps=len(trace["trace_steps"]))


def _validate_step_common(step: dict[str, Any], error_code: str) -> ValidationResult:
    for field in ("step_id", "tick", "operation"):
        if field not in step:
            return _failure(error_code, f"step missing required field {field}")
    if not isinstance(step["tick"], int) or step["tick"] < 0:
        return _failure(error_code, "step tick must be a non-negative integer")
    if step["operation"] not in OPERATIONS:
        return _failure(error_code, "step operation is unsupported")
    return ValidationResult(ok=True)


def _failure(error_code: str, message: str) -> ValidationResult:
    return ValidationResult(ok=False, error_code=error_code, message=message)

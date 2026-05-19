"""ECRP Retry/Replan Contract v1 validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from klein.common.hashing import HashResult, hash_json_artifact, hash_json_value, parse_ijson
from klein.execution.validation import compare_trace_to_runbook

ECRP_POLICY_VERSION = "klein.ecrp_policy.v1"
ALLOWED_STRATEGIES = {"NUDGE_PULSE", "NO_CHANGE", "RETRY_SAME_STEP", "REPLAN_AROUND_FAULT", "ABORT"}
SUCCESS_OUTCOMES = {"SUCCESS", "RECOVERED"}
FAILURE_OUTCOMES = {"FAIL", "PARTIAL", "NO_CHANGE"}


class ECRPError(ValueError):
    """Structured ECRP validation failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class ECRPValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    attempt_count: int = 0
    terminal_failure_status: str = "not_evaluated"


def load_ecrp_policy(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ECRPError("ECRP_POLICY_INVALID", "ECRP policy root must be a JSON object")
    result = validate_ecrp_policy(data)
    if not result.ok:
        raise ECRPError(result.error_code or "ECRP_POLICY_INVALID", result.message or "ECRP policy invalid")
    return data


def canonical_ecrp_policy_hash(policy_or_path: dict[str, Any] | str | Path) -> HashResult:
    if isinstance(policy_or_path, str | Path):
        return hash_json_artifact(Path(policy_or_path))
    return hash_json_value(policy_or_path)


def default_ecrp_policy_for_mode(mode: str) -> dict[str, Any]:
    return {
        "ecrp_policy_version": ECRP_POLICY_VERSION,
        "policy_id": f"default-{mode.lower()}-bounded-failure",
        "mode": mode,
        "max_attempts": 1 if mode in {"HARD", "ENVELOPE"} else 0,
        "allowed_strategies": ["NUDGE_PULSE", "NO_CHANGE"] if mode in {"HARD", "ENVELOPE"} else [],
        "allow_replan": False,
        "allow_success_after_replan": False,
        "allow_success_after_retry": False,
        "allowed_success_strategies": [],
        "requires_trace_evidence": True,
        "terminal_failure_required": True,
    }


def validate_ecrp_policy(policy: dict[str, Any]) -> ECRPValidationResult:
    if policy.get("ecrp_policy_version") != ECRP_POLICY_VERSION:
        return _failure("ECRP_POLICY_SCHEMA_INVALID", "unsupported ecrp_policy_version")
    mode = policy.get("mode")
    if mode not in {"HARD", "ENVELOPE", "DIAGNOSTIC"}:
        return _failure("ECRP_POLICY_SCHEMA_INVALID", "unsupported ECRP policy mode")
    max_attempts = policy.get("max_attempts")
    if not isinstance(max_attempts, int) or max_attempts < 0:
        return _failure("ECRP_POLICY_SCHEMA_INVALID", "max_attempts must be a non-negative integer")
    strategies = policy.get("allowed_strategies")
    if not isinstance(strategies, list):
        return _failure("ECRP_POLICY_SCHEMA_INVALID", "allowed_strategies must be a list")
    unknown = sorted(set(strategies) - ALLOWED_STRATEGIES)
    if unknown:
        return _failure("ECRP_STRATEGY_UNKNOWN", f"unknown ECRP strategies: {', '.join(unknown)}")
    success_strategies = policy.get("allowed_success_strategies", [])
    if not isinstance(success_strategies, list):
        return _failure("ECRP_POLICY_SCHEMA_INVALID", "allowed_success_strategies must be a list")
    unknown_success = sorted(set(success_strategies) - ALLOWED_STRATEGIES)
    if unknown_success:
        return _failure("ECRP_STRATEGY_UNKNOWN", f"unknown ECRP success strategies: {', '.join(unknown_success)}")
    disallowed_success = sorted(set(success_strategies) - set(strategies))
    if disallowed_success:
        return _failure("ECRP_RECOVERY_STRATEGY_NOT_ALLOWED", "allowed_success_strategies must be a subset of allowed_strategies")
    if max_attempts > 0 and not strategies:
        return _failure("ECRP_POLICY_INVALID", "allowed_strategies must be non-empty when max_attempts > 0")
    allow_replan = bool(policy.get("allow_replan"))
    if mode == "HARD" and allow_replan:
        return _failure("ECRP_REPLAN_NOT_ALLOWED", "HARD mode does not allow replan in current alpha")
    if policy.get("allow_success_after_replan") and not allow_replan:
        return _failure("ECRP_POLICY_INVALID", "allow_success_after_replan requires allow_replan")
    if policy.get("allow_success_after_retry") and not success_strategies:
        return _failure("ECRP_POLICY_INVALID", "allow_success_after_retry requires allowed_success_strategies")
    return ECRPValidationResult(ok=True)


def validate_ecrp_attempt_sequence(
    events: list[dict[str, Any]],
    policy: dict[str, Any],
) -> ECRPValidationResult:
    policy_result = validate_ecrp_policy(policy)
    if not policy_result.ok:
        return policy_result
    attempts = [event for event in events if event.get("kind") == "ECRP_ATTEMPT"]
    allowed = set(policy.get("allowed_strategies", []))
    max_attempts = int(policy.get("max_attempts", 0))
    expected_index = 1
    terminal_failure = _has_terminal_failure(events)
    for attempt in attempts:
        if attempt.get("attempt_index") != expected_index:
            return _failure("ECRP_ATTEMPT_SEQUENCE_INVALID", "ECRP attempt_index sequence must start at 1 and be contiguous", len(attempts), _terminal_status(terminal_failure))
        strategy = attempt.get("strategy")
        if strategy not in ALLOWED_STRATEGIES:
            return _failure("ECRP_STRATEGY_UNKNOWN", f"unknown ECRP strategy {strategy}", len(attempts), _terminal_status(terminal_failure))
        if strategy not in allowed:
            return _failure("ECRP_STRATEGY_NOT_ALLOWED", f"ECRP strategy {strategy} is not allowed by policy", len(attempts), _terminal_status(terminal_failure))
        expected_index += 1
    if len(attempts) > max_attempts:
        return _failure("ECRP_ATTEMPTS_EXCEEDED", "ECRP attempts exceeded policy max_attempts", len(attempts), _terminal_status(terminal_failure))
    successful_attempts = [attempt for attempt in attempts if str(attempt.get("outcome")) in SUCCESS_OUTCOMES]
    if successful_attempts:
        if not policy.get("allow_success_after_retry") and not policy.get("allow_success_after_replan"):
            return _failure("ECRP_RECOVERY_SUCCESS_NOT_ALLOWED", "ECRP success is not supported by this policy", len(attempts), _terminal_status(terminal_failure))
        allowed_success = set(policy.get("allowed_success_strategies", []))
        for attempt in successful_attempts:
            if attempt.get("strategy") not in allowed_success:
                return _failure("ECRP_RECOVERY_STRATEGY_NOT_ALLOWED", "ECRP success strategy is not allowed by policy", len(attempts), _terminal_status(terminal_failure))
    if attempts and not successful_attempts and policy.get("terminal_failure_required") and not terminal_failure:
        return _failure("ECRP_TERMINAL_FAILURE_MISSING", "ECRP terminal failure evidence is required", len(attempts), "missing")
    terminal_status = "not_applicable" if successful_attempts else _terminal_status(terminal_failure)
    return ECRPValidationResult(ok=True, attempt_count=len(attempts), terminal_failure_status=terminal_status)


def validate_trace_recovery_contract(
    trace: dict[str, Any],
    runbook: dict[str, Any],
    policy: dict[str, Any],
) -> ECRPValidationResult:
    policy_result = validate_ecrp_policy(policy)
    if not policy_result.ok:
        return policy_result
    comparison = compare_trace_to_runbook(trace, runbook)
    failed_steps = [step for step in trace.get("trace_steps", []) if step.get("status") == "FAILED"]
    trace_claims_success = trace.get("metadata", {}).get("ecrp_recovery_status") == "success"
    if not comparison.ok:
        if comparison.error_code == "TRACE_STEP_MISSING":
            if policy.get("requires_trace_evidence") and not failed_steps:
                if trace_claims_success:
                    return _failure("ECRP_RECOVERY_EVIDENCE_MISSING", "successful recovery trace missing failed original step evidence")
                return _failure("ECRP_TRACE_EVIDENCE_MISSING", "trace missing explicit failed step evidence")
        else:
            return _failure(comparison.error_code or "TRACE_RUNBOOK_MISMATCH", comparison.message or "trace/runbook mismatch")
    recovery_steps = [
        step for step in trace.get("trace_steps", [])
        if step.get("details", {}).get("recovery_attempt_id") or step.get("details", {}).get("recovery_strategy")
    ]
    recovery_attempt_ids = {
        step.get("details", {}).get("recovery_attempt_id")
        for step in recovery_steps
        if step.get("details", {}).get("recovery_attempt_id")
    }
    recovery_attempt_count = len(recovery_attempt_ids) if recovery_attempt_ids else len(recovery_steps)
    successful_recovery_steps = [
        step for step in trace.get("trace_steps", [])
        if step.get("details", {}).get("recovery_status") == "success"
    ]
    if recovery_steps and int(policy.get("max_attempts", 0)) == 0:
        return _failure("ECRP_ATTEMPTS_EXCEEDED", "trace includes recovery steps but policy allows no attempts", recovery_attempt_count)
    if recovery_attempt_count > int(policy.get("max_attempts", 0)):
        return _failure("ECRP_ATTEMPTS_EXCEEDED", "trace recovery attempts exceed policy max_attempts", recovery_attempt_count)
    if trace_claims_success and not successful_recovery_steps:
        return _failure("ECRP_RECOVERY_EVIDENCE_MISSING", "trace claims recovery success without successful retry evidence", recovery_attempt_count)
    if successful_recovery_steps:
        if not policy.get("allow_success_after_retry") and not policy.get("allow_success_after_replan"):
            return _failure("ECRP_RECOVERY_SUCCESS_NOT_ALLOWED", "trace claims recovery success but policy does not permit it", recovery_attempt_count)
        allowed_success = set(policy.get("allowed_success_strategies", []))
        for step in successful_recovery_steps:
            details = step.get("details", {})
            if details.get("recovery_strategy") not in allowed_success:
                return _failure("ECRP_RECOVERY_STRATEGY_NOT_ALLOWED", "trace recovery strategy is not allowed for success", recovery_attempt_count)
            if not step.get("runbook_step_id"):
                return _failure("ECRP_RETRY_STEP_MISSING", "successful retry must reference a runbook step", recovery_attempt_count)
        if not failed_steps:
            return _failure("ECRP_RECOVERY_EVIDENCE_MISSING", "successful recovery trace must include failed original step evidence", recovery_attempt_count)
        if not recovery_steps:
            return _failure("ECRP_RECOVERY_EVIDENCE_MISSING", "successful recovery trace must include recovery attempt evidence", recovery_attempt_count)
    if policy.get("requires_trace_evidence") and not failed_steps and policy.get("terminal_failure_required"):
        return _failure("ECRP_TRACE_EVIDENCE_MISSING", "trace missing explicit failed step evidence")
    terminal_status = "not_applicable" if successful_recovery_steps else ("present" if failed_steps else "not_applicable")
    return ECRPValidationResult(ok=True, attempt_count=recovery_attempt_count, terminal_failure_status=terminal_status)


def _has_terminal_failure(events: list[dict[str, Any]]) -> bool:
    for event in events:
        if event.get("kind") == "DEVICE_EVENT" and event.get("level") == "ERROR":
            code = str(event.get("code", ""))
            if code and code != "ECRP_BOUNDS_EXCEEDED":
                return True
    return False


def _terminal_status(present: bool) -> str:
    return "present" if present else "missing"


def _failure(
    error_code: str,
    message: str,
    attempt_count: int = 0,
    terminal_failure_status: str = "not_evaluated",
) -> ECRPValidationResult:
    return ECRPValidationResult(
        ok=False,
        error_code=error_code,
        message=message,
        attempt_count=attempt_count,
        terminal_failure_status=terminal_failure_status,
    )

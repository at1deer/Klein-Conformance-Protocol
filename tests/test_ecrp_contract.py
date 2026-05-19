from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from klein.conformance.backends import FullSimulatorBackend
from klein.conformance.runner import run_vector
from klein.conformance.suite import discover_vectors
from klein.execution import (
    default_ecrp_policy_for_mode,
    validate_ecrp_attempt_sequence,
    validate_ecrp_policy,
    validate_trace_recovery_contract,
)
from klein.hail.validation import parse_jsonl_events
from klein.tools.ecrp import main as ecrp_main

FIXTURES = Path("tests/fixtures/ecrp")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _events(path: Path) -> list[dict]:
    validation, events = parse_jsonl_events(path.read_text(encoding="utf-8"))
    assert validation.ok, validation.message
    return events


def test_valid_bounded_failure_policy_passes_schema_and_runtime() -> None:
    policy = _load(FIXTURES / "policy_bounded_failure.json")

    Draft7Validator(_load(Path("schemas/ecrp_policy.schema.json"))).validate(policy)
    assert validate_ecrp_policy(policy).ok


def test_invalid_policy_cases_fail_with_contract_codes() -> None:
    unknown = _load(FIXTURES / "policy_invalid_unknown_strategy.json")
    replan = _load(FIXTURES / "policy_invalid_replan_success_without_replan.json")
    hard_replan = {**default_ecrp_policy_for_mode("HARD"), "allow_replan": True}

    assert validate_ecrp_policy(unknown).error_code == "ECRP_STRATEGY_UNKNOWN"
    assert validate_ecrp_policy(replan).error_code == "ECRP_POLICY_INVALID"
    assert validate_ecrp_policy(hard_replan).error_code == "ECRP_REPLAN_NOT_ALLOWED"


def test_successful_retry_policy_requires_explicit_permission() -> None:
    success = _load(FIXTURES / "policy_simulated_recovery_success.json")
    denied = _load(FIXTURES / "policy_recovery_success_not_allowed.json")
    bad_strategy = {**success, "allowed_success_strategies": ["RETRY_SAME_STEP"]}

    Draft7Validator(_load(Path("schemas/ecrp_policy.schema.json"))).validate(success)
    assert validate_ecrp_policy(success).ok
    assert validate_ecrp_attempt_sequence(_events(FIXTURES / "hail_simulated_recovery_success.jsonl"), success).ok
    assert (
        validate_ecrp_attempt_sequence(_events(FIXTURES / "hail_recovery_success_not_allowed.jsonl"), denied).error_code
        == "ECRP_RECOVERY_SUCCESS_NOT_ALLOWED"
    )
    assert validate_ecrp_attempt_sequence(_events(FIXTURES / "hail_simulated_recovery_success.jsonl"), bad_strategy).error_code == "ECRP_RECOVERY_STRATEGY_NOT_ALLOWED"


def test_ecrp_hail_attempt_sequence_contract() -> None:
    policy = _load(FIXTURES / "policy_bounded_failure.json")

    valid = validate_ecrp_attempt_sequence(_events(FIXTURES / "hail_bounded_failure.jsonl"), policy)
    exceeded = validate_ecrp_attempt_sequence(_events(FIXTURES / "hail_attempts_exceed_policy.jsonl"), policy)
    missing_terminal = validate_ecrp_attempt_sequence(_events(FIXTURES / "hail_missing_terminal_failure.jsonl"), policy)

    assert valid.ok
    assert valid.attempt_count == 1
    assert valid.terminal_failure_status == "present"
    assert exceeded.error_code == "ECRP_ATTEMPTS_EXCEEDED"
    assert missing_terminal.error_code == "ECRP_TERMINAL_FAILURE_MISSING"


def test_ecrp_trace_recovery_contract() -> None:
    policy = _load(FIXTURES / "policy_bounded_failure.json")
    runbook = _load(FIXTURES / "runbook_bounded_failure.json")
    trace = _load(FIXTURES / "trace_bounded_failure.json")
    exceeded = _load(FIXTURES / "trace_attempts_exceed_policy.json")
    missing = _load(FIXTURES / "trace_missing_terminal_failure.json")

    assert validate_trace_recovery_contract(trace, runbook, policy).ok
    assert validate_trace_recovery_contract(exceeded, runbook, policy).error_code == "ECRP_ATTEMPTS_EXCEEDED"
    assert validate_trace_recovery_contract(missing, runbook, policy).error_code == "ECRP_TRACE_EVIDENCE_MISSING"


def test_successful_recovery_trace_contract() -> None:
    policy = _load(FIXTURES / "policy_simulated_recovery_success.json")
    denied = _load(FIXTURES / "policy_recovery_success_not_allowed.json")
    runbook = _load(FIXTURES / "runbook_simulated_recovery_success.json")
    trace = _load(FIXTURES / "trace_simulated_recovery_success.json")
    missing_attempt = _load(FIXTURES / "trace_recovery_success_missing_attempt.json")
    missing_failed = _load(FIXTURES / "trace_recovery_success_missing_failed_original.json")

    assert validate_trace_recovery_contract(trace, runbook, policy).ok
    assert validate_trace_recovery_contract(trace, runbook, denied).error_code == "ECRP_RECOVERY_SUCCESS_NOT_ALLOWED"
    assert validate_trace_recovery_contract(missing_attempt, runbook, policy).error_code == "ECRP_RECOVERY_EVIDENCE_MISSING"
    assert validate_trace_recovery_contract(missing_failed, runbook, policy).error_code == "ECRP_RECOVERY_EVIDENCE_MISSING"


def test_no_change_policy_is_explicit_non_recovery_not_success() -> None:
    policy = {**default_ecrp_policy_for_mode("HARD"), "allowed_strategies": ["NO_CHANGE"]}
    events = _events(FIXTURES / "hail_bounded_failure.jsonl")
    for event in events:
        if event.get("kind") == "ECRP_ATTEMPT":
            event["strategy"] = "NO_CHANGE"
            event["outcome"] = "NO_CHANGE"

    assert validate_ecrp_attempt_sequence(events, policy).ok


def test_ecrp_cli_validates_policy_hail_and_trace(capsys) -> None:
    assert ecrp_main(["validate-policy", str(FIXTURES / "policy_bounded_failure.json")]) == 0
    assert ecrp_main([
        "validate-hail",
        "--hail",
        str(FIXTURES / "hail_bounded_failure.jsonl"),
        "--policy",
        str(FIXTURES / "policy_bounded_failure.json"),
    ]) == 0
    assert ecrp_main([
        "validate-trace",
        "--trace",
        str(FIXTURES / "trace_bounded_failure.json"),
        "--runbook",
        str(FIXTURES / "runbook_bounded_failure.json"),
        "--policy",
        str(FIXTURES / "policy_bounded_failure.json"),
    ]) == 0
    assert "ECRP trace contract valid" in capsys.readouterr().out


def test_ecrp_cli_validates_simulated_recovery_success(capsys) -> None:
    assert ecrp_main(["validate-policy", str(FIXTURES / "policy_simulated_recovery_success.json")]) == 0
    assert ecrp_main([
        "validate-hail",
        "--hail",
        str(FIXTURES / "hail_simulated_recovery_success.jsonl"),
        "--policy",
        str(FIXTURES / "policy_simulated_recovery_success.json"),
    ]) == 0
    assert ecrp_main([
        "validate-trace",
        "--trace",
        str(FIXTURES / "trace_simulated_recovery_success.json"),
        "--runbook",
        str(FIXTURES / "runbook_simulated_recovery_success.json"),
        "--policy",
        str(FIXTURES / "policy_simulated_recovery_success.json"),
    ]) == 0
    assert "ECRP trace contract valid" in capsys.readouterr().out


def test_ecrp_contract_reported_for_bounded_failure_vector() -> None:
    vector = discover_vectors(vector_ids=["N014"], suite_dir=Path("tests/vectors/v1"))[0]
    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome.value == "PASS"
    assert result.details["ecrp_policy_present"] is True
    assert result.details["ecrp_contract_status"] == "pass"
    assert result.details["ecrp_attempt_count"] == 1
    assert result.details["ecrp_terminal_failure_status"] == "present"


def test_simulated_recovery_vector_reports_policy_trace_hail_success() -> None:
    vector = discover_vectors(vector_ids=["023"], suite_dir=Path("tests/vectors/v1"))[0]
    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome.value == "PASS"
    assert result.details["run_end_status"] == "SUCCESS"
    assert result.details["trace_recovery_validated"] is True
    assert result.details["ecrp_contract_status"] == "pass"
    assert result.details["ecrp_recovery_status"] == "success"
    assert result.details["ecrp_recovery_strategy"] == "NUDGE_PULSE"

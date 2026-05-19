from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from klein.conformance.backends import FullSimulatorBackend
from klein.conformance.runner import run_vector
from klein.conformance.suite import discover_vectors
from klein.execution import (
    canonical_observation_hash,
    compare_observation_to_trace,
    validate_observation_contract,
    validate_observation_policy,
    validate_observation_snapshot,
)
from klein.tools.observation import main as observation_main

FIXTURES = Path("tests/fixtures/observation")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_valid_observation_policy_and_snapshot_pass_schema_and_runtime() -> None:
    policy = _load(FIXTURES / "policy_simulated_dmf.json")
    snapshot = _load(FIXTURES / "observation_simulated_dmf.json")

    Draft7Validator(_load(Path("schemas/observation_policy.schema.json"))).validate(policy)
    Draft7Validator(_load(Path("schemas/observation_snapshot.schema.json"))).validate(snapshot)
    assert validate_observation_policy(policy).ok
    assert validate_observation_snapshot(snapshot, context={"max_channels": 128, "grid_width": 16, "grid_height": 8}).ok


def test_invalid_observation_snapshots_fail_with_specific_codes() -> None:
    assert validate_observation_snapshot(_load(FIXTURES / "observation_invalid_confidence.json")).error_code == "OBSERVATION_CONFIDENCE_INVALID"
    assert validate_observation_snapshot(_load(FIXTURES / "observation_invalid_hardware_source_alpha.json")).error_code == "OBSERVATION_SOURCE_UNSUPPORTED"
    assert validate_observation_snapshot(_load(FIXTURES / "observation_invalid_attestation_on_simulator.json")).error_code == "OBSERVATION_ATTESTATION_UNSUPPORTED"
    state_oob = _load(FIXTURES / "observation_simulated_dmf.json")
    state_oob["state"]["dmf"]["active_channels"] = [999]
    assert validate_observation_snapshot(state_oob, context={"max_channels": 128}).error_code == "OBSERVATION_DMF_STATE_INVALID"


def test_observation_hash_is_stable_under_key_ordering() -> None:
    snapshot = _load(FIXTURES / "observation_simulated_dmf.json")
    reordered = json.loads(json.dumps(snapshot, sort_keys=True))

    assert canonical_observation_hash(snapshot).ref == canonical_observation_hash(reordered).ref


def test_observation_trace_comparison_and_contract() -> None:
    policy = _load(FIXTURES / "policy_simulated_dmf.json")
    observation = _load(FIXTURES / "observation_simulated_dmf.json")
    mismatch = _load(FIXTURES / "observation_trace_mismatch.json")
    trace = _load(FIXTURES / "trace_simulated_dmf.json")
    runbook = _load(FIXTURES / "runbook_simulated_dmf.json")

    assert compare_observation_to_trace(observation, trace).ok
    assert compare_observation_to_trace(mismatch, trace).error_code == "OBSERVATION_TRACE_MISMATCH"
    assert validate_observation_contract([observation], trace, runbook, policy).ok


def test_recovery_success_observation_contract_requires_snapshot() -> None:
    policy = _load(FIXTURES / "policy_recovery_requires_observation.json")
    observation = _load(FIXTURES / "observation_simulated_dmf_after_recovery.json")
    trace = _load(FIXTURES / "trace_simulated_recovery_success.json")
    runbook = _load(FIXTURES / "runbook_simulated_recovery_success.json")

    assert validate_observation_contract([observation], trace, runbook, policy, recovery_success=True).ok
    assert validate_observation_contract([], trace, runbook, policy, recovery_success=True).error_code == "OBSERVATION_REQUIRED_MISSING"


def test_observation_cli_validates_and_compares(capsys) -> None:
    assert observation_main(["validate-policy", str(FIXTURES / "policy_simulated_dmf.json")]) == 0
    assert observation_main(["validate-snapshot", str(FIXTURES / "observation_simulated_dmf.json")]) == 0
    assert observation_main(["hash", str(FIXTURES / "observation_simulated_dmf.json")]) == 0
    assert observation_main([
        "compare-trace",
        "--observation",
        str(FIXTURES / "observation_simulated_dmf.json"),
        "--trace",
        str(FIXTURES / "trace_simulated_dmf.json"),
    ]) == 0
    assert observation_main([
        "validate-contract",
        "--policy",
        str(FIXTURES / "policy_simulated_dmf.json"),
        "--observation",
        str(FIXTURES / "observation_simulated_dmf.json"),
        "--trace",
        str(FIXTURES / "trace_simulated_dmf.json"),
        "--runbook",
        str(FIXTURES / "runbook_simulated_dmf.json"),
    ]) == 0
    assert "Observation contract valid" in capsys.readouterr().out


def test_observation_details_reported_for_vector_024() -> None:
    vector = discover_vectors(vector_ids=["024"], suite_dir=Path("tests/vectors/v1"))[0]
    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome.value == "PASS"
    assert result.details["observation_present"] is True
    assert result.details["observation_contract_status"] == "pass"
    assert result.details["observation_model"] == "simulated"
    assert result.details["observation_source_type"] == "simulator"

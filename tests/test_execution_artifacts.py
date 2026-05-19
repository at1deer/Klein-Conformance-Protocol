from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from klein.conformance.backends import FullSimulatorBackend
from klein.conformance.runner import run_vector
from klein.conformance.suite import discover_vectors
from klein.execution import (
    build_runbook_from_artifact,
    build_trace_from_runbook,
    canonical_runbook_hash,
    canonical_trace_hash,
    compare_trace_to_runbook,
    validate_execution_trace,
    validate_runbook,
)
from klein.tools.runbook import main as runbook_main
from klein.tools.trace import main as trace_main

FIXTURES = Path("tests/fixtures/execution")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_runbook_and_trace_validate_against_schemas() -> None:
    runbook = _load(FIXTURES / "runbook_minimal_dmf.json")
    trace = _load(FIXTURES / "trace_minimal_dmf.json")

    Draft7Validator(_load(Path("schemas/runbook.schema.json"))).validate(runbook)
    Draft7Validator(_load(Path("schemas/execution_trace.schema.json"))).validate(trace)
    assert validate_runbook(runbook).ok
    assert validate_execution_trace(trace).ok


def test_trace_compare_detects_match_and_mismatch() -> None:
    runbook = _load(FIXTURES / "runbook_minimal_dmf.json")
    trace = _load(FIXTURES / "trace_minimal_dmf.json")
    mismatch = _load(FIXTURES / "trace_mismatch_tick.json")
    missing = _load(FIXTURES / "trace_missing_step.json")

    assert compare_trace_to_runbook(trace, runbook).ok
    assert compare_trace_to_runbook(mismatch, runbook).error_code == "TRACE_RUNBOOK_MISMATCH"
    assert compare_trace_to_runbook(missing, runbook).error_code == "TRACE_STEP_MISSING"


def test_failed_trace_step_is_valid_when_explicit() -> None:
    failed = _load(FIXTURES / "trace_failed_step.json")

    assert validate_execution_trace(failed).ok


def test_runbook_trace_hash_stable_under_reordering(tmp_path: Path) -> None:
    runbook = _load(FIXTURES / "runbook_minimal_dmf.json")
    reordered_path = tmp_path / "runbook.json"
    reordered_path.write_text(json.dumps(runbook, sort_keys=False, indent=4), encoding="utf-8")

    assert canonical_runbook_hash(runbook).ref == canonical_runbook_hash(reordered_path).ref

    trace = _load(FIXTURES / "trace_minimal_dmf.json")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(json.dumps(trace, sort_keys=False, indent=4), encoding="utf-8")
    assert canonical_trace_hash(trace).ref == canonical_trace_hash(trace_path).ref


def test_runbook_builder_uses_container_payload_steps() -> None:
    runbook = build_runbook_from_artifact("tests/vectors/v1/core/002_hard_minimal_container/input/container.kleinc")

    assert runbook["source_artifact_type"] == "container"
    assert runbook["planned_steps"] == []


def test_trace_builder_matches_built_runbook() -> None:
    runbook = _load(FIXTURES / "runbook_minimal_dmf.json")
    trace = build_trace_from_runbook(
        runbook,
        run_id="test-run",
        backend_id="full_simulator",
        backend_version="1.0.0a0",
    )

    assert compare_trace_to_runbook(trace, runbook).ok


def test_execution_artifact_clis(tmp_path: Path, capsys) -> None:
    built = tmp_path / "runbook.json"

    assert runbook_main([
        "build",
        "--artifact",
        "tests/vectors/v1/core/002_hard_minimal_container/input/container.kleinc",
        "--output",
        str(built),
    ]) == 0
    assert runbook_main(["validate", str(built)]) == 0
    assert runbook_main(["hash", str(built)]) == 0
    assert trace_main(["validate", str(FIXTURES / "trace_minimal_dmf.json")]) == 0
    assert trace_main([
        "compare",
        "--runbook",
        str(FIXTURES / "runbook_minimal_dmf.json"),
        "--trace",
        str(FIXTURES / "trace_minimal_dmf.json"),
    ]) == 0
    assert "Trace matches runbook" in capsys.readouterr().out


def test_full_simulator_reports_runbook_trace_details() -> None:
    vector = discover_vectors(vector_ids=["002"], suite_dir=Path("tests/vectors/v1"))[0]
    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome.value == "PASS"
    assert result.details["runbook_present"] is True
    assert result.details["trace_present"] is True
    assert result.details["trace_matches_runbook"] is True
    assert result.details["runbook_hash"].startswith("sha256:")
    assert result.details["trace_hash"].startswith("sha256:")

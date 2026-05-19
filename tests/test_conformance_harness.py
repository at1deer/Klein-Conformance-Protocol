from __future__ import annotations

from pathlib import Path

from klein.conformance.harness import (
    HAIL_GOLDEN_SCHEMA_INVALID,
    VECTOR_EVIDENCE_ASSERTION_FAILED,
    VECTOR_GOLDEN_MISSING,
    VECTOR_INDEX_INVALID,
    VECTOR_METADATA_INVALID,
    CompareMode,
    ConformanceResult,
    ConformanceVector,
    ExecutionResult,
    FullSimulatorBackend,
    Outcome,
    VectorLoadError,
    compare_envelope,
    compare_exact_jsonl,
    discover_vectors,
    envelope_details,
    load_v1_suite,
    parse_args,
    print_failure_details,
    run_vector,
)


class StaticBackend:
    def __init__(self, result: ExecutionResult):
        self._result = result

    @property
    def name(self) -> str:
        return "static"

    def check_capabilities(self, required: list[str]) -> tuple[bool, str]:
        return True, "ok"

    def execute(self, vector: ConformanceVector) -> ExecutionResult:
        return self._result

    def cleanup(self) -> None:
        pass


def negative_vector(expected_error_code: str = "SCHEMA_INVALID") -> ConformanceVector:
    return ConformanceVector(
        id="neg",
        name="negative",
        purpose="negative harness behavior",
        schema_version="legacy-test",
        expected_result="FAIL",
        loose_path=Path("."),
        is_negative=True,
        expected_error_code=expected_error_code,
    )


def evidence_negative_vector() -> ConformanceVector:
    return ConformanceVector(
        id="evidence-neg",
        name="evidence negative",
        purpose="negative evidence assertion behavior",
        schema_version="v1",
        expected_result="FAIL",
        input_type="container",
        input_path=Path("tests/vectors/v1/negative/N014_ecrp_bounded_failure_evidence/input/container.kleinc"),
        is_negative=True,
        expected_error_code="CHANNEL_DEAD",
        metadata={
            "evidence_assertions": [
                {
                    "kind": "DEVICE_EVENT",
                    "where": {"code": "FRAME_FAILED", "level": "INFO"},
                },
                {
                    "kind": "ECRP_ATTEMPT",
                    "where": {
                        "attempt_index": 1,
                        "outcome": "PARTIAL",
                        "strategy": "NUDGE_PULSE",
                    },
                },
                {
                    "kind": "DEVICE_EVENT",
                    "where": {"code": "CHANNEL_DEAD", "level": "ERROR"},
                },
            ]
        },
    )


def device_event(code: str, *, t: int, level: str = "INFO") -> dict:
    return {
        "kind": "DEVICE_EVENT",
        "t": t,
        "timebase": "DEVICE_TICKS",
        "run_id": "R",
        "code": code,
        "level": level,
        "message": code,
    }


def ecrp_event(*, outcome: str = "PARTIAL", strategy: str = "NUDGE_PULSE") -> dict:
    return {
        "kind": "ECRP_ATTEMPT",
        "t": 1,
        "timebase": "DEVICE_TICKS",
        "run_id": "R",
        "attempt_index": 1,
        "strategy": strategy,
        "outcome": outcome,
        "deltas": {"occupancy_shift_cells": 1},
    }


def test_negative_passes_only_on_expected_error_code() -> None:
    result = run_vector(
        negative_vector(),
        StaticBackend(ExecutionResult(success=False, events=[], error_code="SCHEMA_INVALID")),
    )

    assert result.outcome == Outcome.PASS


def test_negative_fails_on_error_mismatch() -> None:
    result = run_vector(
        negative_vector(),
        StaticBackend(ExecutionResult(success=False, events=[], error_code="OUTPUT_MISMATCH")),
    )

    assert result.outcome == Outcome.FAIL
    assert result.reason == "negative_error_mismatch"


def test_negative_fails_on_unexpected_success() -> None:
    result = run_vector(
        negative_vector(),
        StaticBackend(ExecutionResult(success=True, events=[{"kind": "DEVICE_EVENT"}])),
    )

    assert result.outcome == Outcome.FAIL
    assert result.reason == "negative_unexpected_pass"


def test_negative_fails_when_error_code_missing() -> None:
    result = run_vector(
        negative_vector(),
        StaticBackend(ExecutionResult(success=False, events=[])),
    )

    assert result.outcome == Outcome.FAIL
    assert result.reason == "negative_error_mismatch"


def test_evidence_negative_fails_when_ecrp_attempt_absent() -> None:
    events = [
        device_event("FRAME_FAILED", t=1),
        device_event("CHANNEL_DEAD", t=1, level="ERROR"),
    ]

    result = run_vector(
        evidence_negative_vector(),
        StaticBackend(ExecutionResult(success=False, events=events, error_code="CHANNEL_DEAD")),
    )

    assert result.outcome == Outcome.FAIL
    assert result.reason == "negative_evidence_assertion_failed"
    assert result.details["evidence_error_code"] == VECTOR_EVIDENCE_ASSERTION_FAILED


def test_evidence_negative_fails_when_ecrp_outcome_changes() -> None:
    events = [
        device_event("FRAME_FAILED", t=1),
        ecrp_event(outcome="NO_CHANGE"),
        device_event("CHANNEL_DEAD", t=1, level="ERROR"),
    ]

    result = run_vector(
        evidence_negative_vector(),
        StaticBackend(ExecutionResult(success=False, events=events, error_code="CHANNEL_DEAD")),
    )

    assert result.outcome == Outcome.FAIL
    assert result.reason == "negative_evidence_assertion_failed"


def test_evidence_negative_fails_when_error_occurs_without_ecrp() -> None:
    events = [device_event("CHANNEL_DEAD", t=1, level="ERROR")]

    result = run_vector(
        evidence_negative_vector(),
        StaticBackend(ExecutionResult(success=False, events=events, error_code="CHANNEL_DEAD")),
    )

    assert result.outcome == Outcome.FAIL
    assert result.reason == "negative_evidence_assertion_failed"


def test_v1_negative_without_evidence_assertions_still_passes_on_error_code() -> None:
    vector = ConformanceVector(
        id="ordinary-neg",
        name="ordinary negative",
        purpose="ordinary negative",
        schema_version="v1",
        expected_result="FAIL",
        input_type="hail_jsonl",
        input_path=Path("tests/vectors/v1/negative/N002_hail_missing_device_message/input/observables.jsonl"),
        is_negative=True,
        expected_error_code="HAIL_SCHEMA_INVALID",
    )

    result = run_vector(
        vector,
        StaticBackend(ExecutionResult(success=False, events=[], error_code="HAIL_SCHEMA_INVALID")),
    )

    assert result.outcome == Outcome.PASS


def test_hard_mode_exact_compare_requires_canonical_match() -> None:
    ok, _ = compare_exact_jsonl(
        [{"kind": "DEVICE_EVENT", "t": 0, "code": "B"}],
        [{"kind": "DEVICE_EVENT", "t": 0, "code": "A"}],
    )

    assert not ok


def test_envelope_mode_accepts_declared_tick_tolerance() -> None:
    ok, msg = compare_envelope(
        [{"kind": "DEVICE_EVENT", "t": 2, "code": "A"}],
        [{"kind": "DEVICE_EVENT", "t": 1, "code": "A"}],
        tolerances={"t": 1},
    )

    assert ok, msg


def test_envelope_mode_rejects_tick_outside_tolerance() -> None:
    ok, msg = compare_envelope(
        [{"kind": "DEVICE_EVENT", "t": 3, "code": "A"}],
        [{"kind": "DEVICE_EVENT", "t": 1, "code": "A"}],
        tolerances={"t": 1},
    )

    assert not ok
    assert "outside tolerance" in msg


def test_envelope_mode_rejects_event_count_mismatch() -> None:
    ok, msg = compare_envelope(
        [{"kind": "DEVICE_EVENT", "t": 1, "code": "A"}],
        [
            {"kind": "DEVICE_EVENT", "t": 1, "code": "A"},
            {"kind": "DEVICE_EVENT", "t": 2, "code": "B"},
        ],
        tolerances={"t": 1},
    )

    assert not ok
    assert "Event count mismatch" in msg
    assert envelope_details(
        [{"kind": "DEVICE_EVENT", "t": 1, "code": "A"}],
        [
            {"kind": "DEVICE_EVENT", "t": 1, "code": "A"},
            {"kind": "DEVICE_EVENT", "t": 2, "code": "B"},
        ],
        tolerances={"t": 1},
    )["reason"] == "event_count_mismatch"


def test_envelope_mode_rejects_event_kind_mismatch() -> None:
    ok, msg = compare_envelope(
        [{"kind": "MEASUREMENT", "t": 1, "measurement_id": "A"}],
        [{"kind": "DEVICE_EVENT", "t": 1, "code": "A"}],
        tolerances={"t": 1},
    )

    assert not ok
    assert "Kind mismatch" in msg
    details = envelope_details(
        [{"kind": "MEASUREMENT", "t": 1, "measurement_id": "A"}],
        [{"kind": "DEVICE_EVENT", "t": 1, "code": "A"}],
        tolerances={"t": 1},
    )
    assert details["margins"][0]["reason"] == "kind_mismatch"


def test_envelope_details_records_tick_margin() -> None:
    details = envelope_details(
        [{"kind": "DEVICE_EVENT", "t": 2, "code": "A"}],
        [{"kind": "DEVICE_EVENT", "t": 1, "code": "A"}],
        tolerances={"t": 2},
    )

    assert details["tolerances"] == {"t": 2}
    assert details["margins"][0]["delta"] == 1
    assert details["margins"][0]["margin"] == 1
    assert details["margins"][0]["within"] is True


def test_v1_vector_without_declared_input_fails() -> None:
    vector = ConformanceVector(
        id="missing",
        name="missing",
        purpose="v1 requires declared input",
        schema_version="v1",
        expected_result="PASS",
        comparison_mode=CompareMode.EXACT_JSONL,
    )

    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome == Outcome.FAIL
    assert result.actual_error_code == "VECTOR_INPUT_MISSING"
    assert result.reason == "v1_input_missing"


def test_cli_list_vectors_alias_sets_list_mode() -> None:
    args = parse_args(["--list-vectors"])

    assert args.list_only is True


def test_cli_suite_integrity_flag_sets_check_mode() -> None:
    args = parse_args(["--check-suite-integrity"])

    assert args.check_suite_integrity is True


def test_cli_failure_detail_output_includes_error_codes(capsys) -> None:
    print_failure_details(
        [
            ConformanceResult(
                vector_id="NTEST",
                vector_name="negative",
                outcome=Outcome.FAIL,
                message="failed as expected",
                expected_result="FAIL",
                actual_result="FAIL",
                expected_error_code="EXPECTED",
                actual_error_code="ACTUAL",
                validation_stage="hail_schema",
                reason="negative_error_code_mismatch",
            )
        ],
        limit=1,
    )

    output = capsys.readouterr().out
    assert "NTEST" in output
    assert "EXPECTED" in output
    assert "ACTUAL" in output


def test_v1_golden_only_vector_cannot_pass_with_synthetic_backend() -> None:
    event = {
        "kind": "DEVICE_EVENT",
        "t": 0,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "code": "INIT",
        "level": "INFO",
        "message": "ok",
    }
    vector = ConformanceVector(
        id="golden-only",
        name="golden-only",
        purpose="golden-only v1 vectors are invalid",
        schema_version="v1",
        expected_result="PASS",
        golden_observables=[event],
    )

    result = run_vector(vector, StaticBackend(ExecutionResult(success=True, events=[event])))

    assert result.outcome == Outcome.FAIL
    assert result.actual_error_code == "VECTOR_INPUT_MISSING"


def test_hail_jsonl_input_negative_vectors_have_expected_codes() -> None:
    vectors = {
        vector.id: vector
        for vector in discover_vectors(
            vector_ids=["N002", "N003"],
            suite_dir=Path("tests/vectors/v1"),
        )
    }
    backend = FullSimulatorBackend()

    try:
        for vector_id in ["N002", "N003"]:
            result = run_vector(vectors[vector_id], backend)
            assert result.outcome == Outcome.PASS
            assert result.actual_error_code == "HAIL_SCHEMA_INVALID"
            assert result.validation_stage == "hail_schema"
    finally:
        backend.cleanup()


def test_comparison_details_record_normalization_and_digests() -> None:
    vector = ConformanceVector(
        id="norm",
        name="normalization",
        purpose="comparison metadata",
        schema_version="legacy-test",
        expected_result="PASS",
        loose_path=Path("."),
        normalize_run_metadata=True,
        golden_observables=[
            {
                "kind": "DEVICE_EVENT",
                "t": 0,
                "run_id": "expected",
                "code": "INIT",
            }
        ],
    )
    result = run_vector(
        vector,
        StaticBackend(
            ExecutionResult(
                success=True,
                events=[
                    {
                        "kind": "DEVICE_EVENT",
                        "t": 0,
                        "run_id": "actual",
                        "code": "INIT",
                    }
                ],
            )
        ),
    )

    assert result.outcome == Outcome.PASS
    assert result.details["normalized_run_metadata"] is True
    assert result.details["digest_actual"] == result.details["digest_expected"]


def write_json(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def test_index_vectors_as_strings_fails_cleanly(tmp_path: Path) -> None:
    write_json(tmp_path / "index.json", '{"vectors":["001"]}')

    try:
        load_v1_suite(tmp_path)
    except VectorLoadError as exc:
        assert exc.error_code == VECTOR_INDEX_INVALID
    else:
        raise AssertionError("expected VectorLoadError")


def test_duplicate_ids_fail_cleanly(tmp_path: Path) -> None:
    for folder in ["a", "b"]:
        write_json(tmp_path / folder / "vector.json", "{}")
    write_json(
        tmp_path / "index.json",
        '{"vectors":[{"id":"001","folder":"a"},{"id":"001","folder":"b"}]}',
    )

    try:
        load_v1_suite(tmp_path)
    except VectorLoadError as exc:
        assert exc.error_code == VECTOR_INDEX_INVALID
    else:
        raise AssertionError("expected VectorLoadError")


def test_missing_folder_fails_cleanly(tmp_path: Path) -> None:
    write_json(tmp_path / "index.json", '{"vectors":[{"id":"001","folder":"missing"}]}')

    try:
        load_v1_suite(tmp_path)
    except VectorLoadError as exc:
        assert exc.error_code == VECTOR_INDEX_INVALID
    else:
        raise AssertionError("expected VectorLoadError")


def test_missing_input_type_fails_cleanly(tmp_path: Path) -> None:
    folder = tmp_path / "v"
    write_json(tmp_path / "index.json", '{"vectors":[{"id":"001","folder":"v"}]}')
    write_json(
        folder / "vector.json",
        '{"id":"001","name":"bad","schema_version":"v1","profile":"core",'
        '"mode":"HARD","expected_result":"PASS","input_path":"input/a.jsonl",'
        '"comparison_mode":"EXACT_JSONL"}',
    )

    try:
        load_v1_suite(tmp_path)
    except VectorLoadError as exc:
        assert exc.error_code == VECTOR_METADATA_INVALID
    else:
        raise AssertionError("expected VectorLoadError")


def test_negative_without_expected_error_code_fails_cleanly(tmp_path: Path) -> None:
    folder = tmp_path / "v"
    write_json(tmp_path / "index.json", '{"vectors":[{"id":"N001","folder":"v"}]}')
    write_json(
        folder / "vector.json",
        '{"id":"N001","name":"bad","schema_version":"v1","profile":"core",'
        '"mode":"HARD","expected_result":"FAIL","input_type":"hail_jsonl",'
        '"input_path":"input/a.jsonl","comparison_mode":"EXACT_JSONL"}',
    )

    try:
        load_v1_suite(tmp_path)
    except VectorLoadError as exc:
        assert exc.error_code == VECTOR_METADATA_INVALID
    else:
        raise AssertionError("expected VectorLoadError")


def test_v1_positive_missing_golden_fails_with_canonical_code() -> None:
    vector = ConformanceVector(
        id="missing-golden",
        name="missing golden",
        purpose="golden required",
        schema_version="v1",
        expected_result="PASS",
        input_type="hail_jsonl",
        input_path=Path("tests/vectors/v1/core/003_envelope_minimal_tolerance/input/observables.jsonl"),
    )

    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome == Outcome.FAIL
    assert result.actual_error_code == VECTOR_GOLDEN_MISSING


def test_v1_positive_invalid_golden_fails_before_comparison() -> None:
    vector = ConformanceVector(
        id="bad-golden",
        name="bad golden",
        purpose="golden invalid",
        schema_version="v1",
        expected_result="PASS",
        input_type="hail_jsonl",
        input_path=Path("tests/vectors/v1/core/003_envelope_minimal_tolerance/input/observables.jsonl"),
        golden_error_code=HAIL_GOLDEN_SCHEMA_INVALID,
        golden_validation_stage="json_parse",
        golden_error_index=0,
    )

    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome == Outcome.FAIL
    assert result.actual_error_code == HAIL_GOLDEN_SCHEMA_INVALID
    assert result.details["line_index"] == 0


def test_v1_negative_does_not_require_golden() -> None:
    vector = ConformanceVector(
        id="neg-no-golden",
        name="negative no golden",
        purpose="negative golden optional",
        schema_version="v1",
        expected_result="FAIL",
        input_type="project",
        input_path=Path("tests/vectors/v1/negative/N001_missing_input_artifact/input/missing.klein"),
        is_negative=True,
        expected_error_code="VECTOR_INPUT_MISSING",
    )

    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome == Outcome.PASS


def test_strict_v1_negative_evidence_emits_no_legacy_recovery_terms() -> None:
    vector = discover_vectors(
        vector_ids=["N014"],
        suite_dir=Path("tests/vectors/v1"),
    )[0]
    backend = FullSimulatorBackend()

    try:
        result = backend.execute(vector)
    finally:
        backend.cleanup()

    assert result.success is False
    serialized = "\n".join(str(event) for event in result.events)
    assert "LCP_" not in serialized
    assert "DSB_" not in serialized
    assert "RSB_" not in serialized

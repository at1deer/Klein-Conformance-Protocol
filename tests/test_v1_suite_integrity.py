from __future__ import annotations

import json
from pathlib import Path

from klein.conformance.harness import check_v1_suite_integrity


def test_authoritative_v1_suite_has_no_integrity_issues() -> None:
    issues = check_v1_suite_integrity(Path("tests/vectors/v1"))

    assert issues == []


def test_suite_integrity_reports_duplicate_ids(tmp_path: Path) -> None:
    suite = tmp_path / "v1"
    suite.mkdir()
    (suite / "index.json").write_text(
        json.dumps({
            "suite_version": "v1",
            "vectors": [
                {"id": "001", "folder": "core/one"},
                {"id": "001", "folder": "core/two"},
            ],
        }),
        encoding="utf-8",
    )

    issues = check_v1_suite_integrity(suite)

    assert any("Duplicate v1 vector id 001" in issue["message"] for issue in issues)


def test_suite_integrity_reports_duplicate_names(tmp_path: Path) -> None:
    suite = tmp_path / "v1"
    for folder in (suite / "core" / "one", suite / "core" / "two"):
        (folder / "input").mkdir(parents=True)
        (folder / "golden").mkdir()
        (folder / "expected").mkdir()
        (folder / "input" / "observables.jsonl").write_text(VALID_DEVICE_EVENT, encoding="utf-8")
        (folder / "golden" / "observables.jsonl").write_text(VALID_DEVICE_EVENT, encoding="utf-8")
        vector_id = "001" if folder.name == "one" else "002"
        (folder / "vector.json").write_text(
            json.dumps({
                "id": vector_id,
                "name": "duplicate_name",
                "schema_version": "v1",
                "profile": "core",
                "mode": "HARD",
                "expected_result": "PASS",
                "input_type": "hail_jsonl",
                "input_path": "input/observables.jsonl",
                "comparison_mode": "EXACT_JSONL",
            }),
            encoding="utf-8",
        )
    (suite / "index.json").write_text(
        json.dumps({
            "suite_version": "v1",
            "vectors": [
                {"id": "001", "folder": "core/one"},
                {"id": "002", "folder": "core/two"},
            ],
        }),
        encoding="utf-8",
    )

    issues = check_v1_suite_integrity(suite)

    assert any("Duplicate v1 vector name duplicate_name" in issue["message"] for issue in issues)


def test_suite_integrity_reports_unindexed_vector_directories(tmp_path: Path) -> None:
    suite = tmp_path / "v1"
    (suite / "core" / "orphan" / "golden").mkdir(parents=True)
    (suite / "index.json").write_text(
        json.dumps({"suite_version": "v1", "vectors": []}),
        encoding="utf-8",
    )

    issues = check_v1_suite_integrity(suite)

    assert any("Unindexed v1 vector directory: core/orphan" in issue["message"] for issue in issues)


VALID_DEVICE_EVENT = (
    '{"kind":"DEVICE_EVENT","t":0,"timebase":"DEVICE_TICKS","run_id":"R",'
    '"code":"INIT","level":"INFO","message":"ok"}\n'
)

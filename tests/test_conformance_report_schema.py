from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft7Validator

from klein.conformance.cli import main


def load_report_schema() -> dict:
    return json.loads(Path("schemas/conformance_report.schema.json").read_text(encoding="utf-8"))


def run_json_report(args: list[str], capsys) -> tuple[int, dict]:
    code = main([*args, "--json"])
    output = capsys.readouterr().out
    return code, json.loads(output)


def assert_valid_report(report: dict) -> None:
    Draft7Validator(load_report_schema()).validate(report)


def test_v1_positive_json_report_matches_schema(capsys) -> None:
    code, report = run_json_report(
        ["--suite", "tests/vectors/v1", "--vector", "001", "--backend", "full_simulator"],
        capsys,
    )

    assert code == 0
    assert_valid_report(report)
    assert report["summary"]["authoritative_v1"] is True
    assert report["summary"]["legacy_namespace"] is False
    details = report["results"][0]["details"]
    assert details["input_artifact_hash"].startswith("sha256:")
    assert details["input_artifact_canonicalization"] == "klein.canon.json.v1"
    assert details["profile_id"] == "core"
    assert details["backend_id"] == "full_simulator"
    assert details["hail_chain_algorithm"] == "klein.hail.chain.v1"
    assert details["hail_chain_matches_run_end"] is True
    assert details["hail_chain_canonical_order_ok"] is True


def test_v1_signed_conformance_json_report_matches_schema(capsys) -> None:
    code, report = run_json_report(
        ["--suite", "tests/vectors/v1", "--vector", "012", "--backend", "full_simulator"],
        capsys,
    )

    assert code == 0
    assert_valid_report(report)
    details = report["results"][0]["details"]
    assert details["signed_conformance"] is True
    assert details["run_manifest_present"] is True
    assert details["run_manifest_verified"] is True
    assert details["run_manifest_signature_status"] == "valid"
    assert details["run_manifest_trust_status"] == "trusted"
    assert details["run_manifest_key_id"] == "klein-test-backend-001"
    assert details["run_manifest_signature_algorithm"] == "Ed25519"


def test_v1_negative_json_report_matches_schema(capsys) -> None:
    code, report = run_json_report(
        ["--suite", "tests/vectors/v1", "--vector", "N002", "--backend", "full_simulator"],
        capsys,
    )

    assert code == 0
    assert_valid_report(report)
    assert report["results"][0]["expected_error_code"] == "HAIL_SCHEMA_INVALID"
    details = report["results"][0]["details"]
    assert details["input_raw_sha256"].startswith("sha256:")
    assert details["input_artifact_hash"] is None
    assert details["input_artifact_hash_error"] == "HAIL_SCHEMA_INVALID"


def test_legacy_json_report_matches_schema_without_authority(capsys) -> None:
    code, report = run_json_report(
        ["--suite", "tests/vectors", "--legacy", "--smoke", "--backend", "full_simulator"],
        capsys,
    )

    assert code == 1
    assert_valid_report(report)
    assert report["summary"]["authoritative_v1"] is False
    assert report["summary"]["legacy_namespace"] is True


def test_mock_backend_json_report_is_non_authoritative(capsys) -> None:
    code, report = run_json_report(
        ["--suite", "tests/vectors/v1", "--vector", "004", "--backend", "mock"],
        capsys,
    )

    assert code == 0
    assert_valid_report(report)
    assert report["summary"]["authoritative_v1"] is False
    assert report["summary"]["legacy_namespace"] is True

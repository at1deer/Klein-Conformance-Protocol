from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

RUST_MANIFEST = Path("verifiers/rust/Cargo.toml")
FIXTURE_INDEX = Path("tests/fixtures/cross_language/fixtures.json")
VALID_BUNDLE = Path("tests/fixtures/run_bundle/valid_signed_run.kcprun")


def _cargo() -> str:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    return cargo


def test_rust_verifier_cross_language_fixtures() -> None:
    result = subprocess.run(
        [
            _cargo(),
            "run",
            "--manifest-path",
            str(RUST_MANIFEST),
            "--",
            "verify-fixtures",
            str(FIXTURE_INDEX),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Klein Rust verifier: 106 fixtures passed, 0 failed" in result.stdout


def test_rust_verifier_valid_bundle_cli() -> None:
    result = subprocess.run(
        [
            _cargo(),
            "run",
            "--manifest-path",
            str(RUST_MANIFEST),
            "--",
            "verify-bundle",
            str(VALID_BUNDLE),
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    assert "Klein Rust bundle verifier: pass" in result.stdout
    assert "klein-test-backend-001" in result.stdout


def test_rust_verifier_bundle_json_matches_independent_schema() -> None:
    result = subprocess.run(
        [
            _cargo(),
            "run",
            "--manifest-path",
            str(RUST_MANIFEST),
            "--",
            "verify-bundle",
            str(VALID_BUNDLE),
            "--json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )

    payload = json.loads(result.stdout)
    schema = json.loads(Path("schemas/independent_verifier_result.schema.json").read_text())
    Draft7Validator(schema).validate(payload)

    python_result = subprocess.run(
        [
            sys.executable,
            "-m",
            "klein.tools.verify_bundle",
            str(VALID_BUNDLE),
            "--json",
        ],
        check=True,
        text=True,
        capture_output=True,
    )
    expected = json.loads(python_result.stdout)
    assert payload["overall_status"] == expected["overall_status"]
    assert payload["checks"] == expected["checks"]
    assert payload["bindings"]["trusted_key_ids"] == expected["bindings"]["trusted_key_ids"]

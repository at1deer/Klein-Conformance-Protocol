from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

RUST_MANIFEST = Path("verifiers/rust/Cargo.toml")
VALID_BUNDLE = Path("tests/fixtures/run_bundle/valid_signed_run.kcprun")

CORE_CHECKS = {
    "bundle_schema",
    "bundle_entry_hashes",
    "hail_schema",
    "hail_canonicalization",
    "hail_ordering",
    "hail_lifecycle",
    "hail_chain",
    "run_manifest_schema",
    "run_manifest_payload",
    "run_manifest_signature",
    "trust_policy_schema",
    "trust_policy_authorization",
    "conformance_report",
}

CORE_BINDINGS = {
    "artifact_hash",
    "hail_digest",
    "hail_chain_digest",
    "backend_id",
    "profile_id",
    "profile_version",
    "substrate_fingerprint",
    "trusted_key_ids",
}


def _cargo() -> str:
    cargo = shutil.which("cargo")
    if cargo is None:
        pytest.skip("cargo is not available")
    return cargo


def _rust_result() -> dict:
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
    return json.loads(result.stdout)


def _python_result() -> dict:
    result = subprocess.run(
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
    return json.loads(result.stdout)


def test_rust_python_independent_verifier_semantic_parity() -> None:
    rust = _rust_result()
    python = _python_result()

    assert rust["overall_status"] == python["overall_status"]
    for check in CORE_CHECKS:
        assert rust["checks"][check] == python["checks"][check]
    for binding in CORE_BINDINGS:
        assert rust["bindings"][binding] == python["bindings"][binding]

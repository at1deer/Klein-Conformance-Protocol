from __future__ import annotations

from pathlib import Path

from klein.attestation import (
    canonical_attestation_profile_hash,
    canonical_attestation_statement_hash,
    inspect_attestation_statement,
    validate_attestation_profile,
    validate_attestation_statement,
    verify_attestation_statement_binding,
)
from klein.common.hashing import parse_ijson
from klein.tools.attestation import main as attestation_cli_main

FIXTURE_DIR = Path("tests/fixtures/attestation")
BACKEND_ID = "opendrop_ewod_dry_run"
BACKEND_HASH = "sha256:6666666666666666666666666666666666666666666666666666666666666666"
RECORDED_RUN_HASH = "sha256:5555555555555555555555555555555555555555555555555555555555555555"
MISMATCH_HASH = "sha256:8888888888888888888888888888888888888888888888888888888888888888"


def load_fixture(name: str) -> dict:
    data = parse_ijson((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_valid_profile_passes() -> None:
    result = validate_attestation_profile(load_fixture("profile_mock_none.json"))
    assert result.ok


def test_hardware_attestation_profile_fails_current_alpha() -> None:
    result = validate_attestation_profile(load_fixture("profile_invalid_claims_hardware_attestation.json"))
    assert not result.ok
    assert result.error_code == "ATTESTATION_HARDWARE_UNSUPPORTED"


def test_valid_none_statement_passes_and_inspects_as_none() -> None:
    statement = load_fixture("statement_none_recorded_run.json")
    result = validate_attestation_statement(statement)
    inspection = inspect_attestation_statement(statement)
    assert result.ok
    assert inspection.attestation_status == "none"
    assert inspection.hardware_attestation_claimed is False


def test_valid_mock_statement_passes_and_inspects_as_mock() -> None:
    statement = load_fixture("statement_mock_backend.json")
    result = validate_attestation_statement(statement)
    inspection = inspect_attestation_statement(statement)
    assert result.ok
    assert inspection.attestation_status == "mock"
    assert inspection.backend_id == BACKEND_ID


def test_statement_with_hardware_attestation_claim_fails_current_alpha() -> None:
    result = validate_attestation_statement(load_fixture("statement_invalid_claims_hardware_attestation.json"))
    assert not result.ok
    assert result.error_code == "ATTESTATION_HARDWARE_UNSUPPORTED"


def test_statement_with_hardware_root_fails_current_alpha() -> None:
    result = validate_attestation_statement(load_fixture("statement_invalid_hardware_root_current_alpha.json"))
    assert not result.ok
    assert result.error_code == "ATTESTATION_HARDWARE_ROOT_UNSUPPORTED"


def test_statement_with_quote_fails_current_alpha() -> None:
    result = validate_attestation_statement(load_fixture("statement_invalid_quote_current_alpha.json"))
    assert not result.ok
    assert result.error_code == "ATTESTATION_QUOTE_UNSUPPORTED"


def test_statement_with_signature_fails_current_alpha() -> None:
    result = validate_attestation_statement(load_fixture("statement_invalid_signature_current_alpha.json"))
    assert not result.ok
    assert result.error_code == "ATTESTATION_SIGNATURE_UNSUPPORTED"


def test_subject_hash_mismatch_fails_binding_check() -> None:
    result = verify_attestation_statement_binding(
        load_fixture("statement_invalid_hash_mismatch.json"),
        subject_hash=BACKEND_HASH,
    )
    assert not result.ok
    assert result.error_code == "ATTESTATION_SUBJECT_HASH_MISMATCH"


def test_backend_mismatch_fails_binding_check() -> None:
    result = verify_attestation_statement_binding(
        load_fixture("statement_invalid_backend_mismatch.json"),
        backend_id=BACKEND_ID,
    )
    assert not result.ok
    assert result.error_code == "ATTESTATION_BACKEND_MISMATCH"


def test_create_mock_cli_produces_valid_statement(tmp_path: Path) -> None:
    output = tmp_path / "mock_attestation.json"
    rc = attestation_cli_main(
        [
            "create-mock",
            "--subject-type",
            "backend",
            "--backend-id",
            BACKEND_ID,
            "--subject-hash",
            BACKEND_HASH,
            "--output",
            str(output),
        ]
    )
    assert rc == 0
    statement = parse_ijson(output.read_text(encoding="utf-8"))
    assert isinstance(statement, dict)
    assert validate_attestation_statement(statement).ok
    assert verify_attestation_statement_binding(statement, subject_hash=BACKEND_HASH, backend_id=BACKEND_ID).ok


def test_create_none_cli_produces_valid_statement(tmp_path: Path) -> None:
    output = tmp_path / "none_attestation.json"
    rc = attestation_cli_main(
        [
            "create-none",
            "--subject-type",
            "recorded_run",
            "--subject-id",
            "opendrop_dry_run_recorded_run",
            "--subject-hash",
            RECORDED_RUN_HASH,
            "--output",
            str(output),
        ]
    )
    assert rc == 0
    statement = parse_ijson(output.read_text(encoding="utf-8"))
    assert isinstance(statement, dict)
    assert validate_attestation_statement(statement).ok
    assert inspect_attestation_statement(statement).attestation_status == "none"


def test_hash_stable_under_key_ordering() -> None:
    statement = load_fixture("statement_mock_backend.json")
    reordered = {
        "metadata": statement["metadata"],
        "signature": statement["signature"],
        "measurements": statement["measurements"],
        "quote": statement["quote"],
        "hardware_root": statement["hardware_root"],
        "hardware_attestation_claimed": statement["hardware_attestation_claimed"],
        "backend": statement["backend"],
        "subject": statement["subject"],
        "statement_kind": statement["statement_kind"],
        "statement_id": statement["statement_id"],
        "attestation_statement_version": statement["attestation_statement_version"],
    }
    assert canonical_attestation_statement_hash(statement).ref == canonical_attestation_statement_hash(reordered).ref

    profile = load_fixture("profile_mock_none.json")
    assert canonical_attestation_profile_hash(profile).ref == canonical_attestation_profile_hash(
        dict(reversed(profile.items()))
    ).ref


def test_verify_binding_accepts_fixture_subject_and_backend() -> None:
    statement = load_fixture("statement_mock_backend.json")
    assert verify_attestation_statement_binding(statement, subject_hash=BACKEND_HASH, backend_id=BACKEND_ID).ok
    assert not verify_attestation_statement_binding(statement, subject_hash=MISMATCH_HASH).ok

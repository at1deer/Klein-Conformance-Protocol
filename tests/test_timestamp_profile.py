from __future__ import annotations

from pathlib import Path

from klein.common.hashing import parse_ijson
from klein.timestamping import (
    canonical_timestamp_profile_hash,
    canonical_timestamp_token_hash,
    inspect_timestamp_token,
    validate_timestamp_profile,
    validate_timestamp_token,
    verify_timestamp_token_binding,
)
from klein.tools.timestamp import main as timestamp_cli_main

FIXTURE_DIR = Path("tests/fixtures/timestamp")
BUNDLE_HASH = "sha256:1111111111111111111111111111111111111111111111111111111111111111"
MISMATCH_HASH = "sha256:4444444444444444444444444444444444444444444444444444444444444444"


def load_fixture(name: str) -> dict:
    data = parse_ijson((FIXTURE_DIR / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_valid_profile_passes() -> None:
    result = validate_timestamp_profile(load_fixture("profile_mock_local.json"))
    assert result.ok


def test_trusted_time_profile_fails_current_alpha() -> None:
    result = validate_timestamp_profile(load_fixture("profile_invalid_claims_trusted_time.json"))
    assert not result.ok
    assert result.error_code == "TIMESTAMP_TRUSTED_TIME_UNSUPPORTED"


def test_valid_mock_token_passes_and_inspects_as_mock() -> None:
    token = load_fixture("token_mock_bundle.json")
    result = validate_timestamp_token(token)
    inspection = inspect_timestamp_token(token)
    assert result.ok
    assert inspection.timestamp_status == "mock"
    assert inspection.trusted_time_claimed is False


def test_token_with_trusted_time_claim_fails_current_alpha() -> None:
    result = validate_timestamp_token(load_fixture("token_invalid_claims_trusted_time.json"))
    assert not result.ok
    assert result.error_code == "TIMESTAMP_TRUSTED_TIME_UNSUPPORTED"


def test_tsa_token_fails_current_alpha() -> None:
    result = validate_timestamp_token(load_fixture("token_invalid_tsa_current_alpha.json"))
    assert not result.ok
    assert result.error_code == "TIMESTAMP_TSA_UNSUPPORTED"


def test_target_hash_mismatch_fails_binding_check() -> None:
    result = verify_timestamp_token_binding(load_fixture("token_invalid_hash_mismatch.json"), BUNDLE_HASH)
    assert not result.ok
    assert result.error_code == "TIMESTAMP_TARGET_HASH_MISMATCH"


def test_bad_time_fails() -> None:
    result = validate_timestamp_token(load_fixture("token_invalid_bad_time.json"))
    assert not result.ok
    assert result.error_code == "TIMESTAMP_TIME_INVALID"


def test_create_mock_cli_produces_valid_token(tmp_path: Path) -> None:
    output = tmp_path / "mock_timestamp.json"
    rc = timestamp_cli_main(
        [
            "create-mock",
            "--target-type",
            "run_bundle",
            "--target-hash",
            BUNDLE_HASH,
            "--output",
            str(output),
        ]
    )
    assert rc == 0
    token = parse_ijson(output.read_text(encoding="utf-8"))
    assert isinstance(token, dict)
    assert validate_timestamp_token(token).ok
    assert verify_timestamp_token_binding(token, BUNDLE_HASH).ok


def test_hash_stable_under_key_ordering() -> None:
    token = load_fixture("token_mock_bundle.json")
    reordered = {
        "metadata": token["metadata"],
        "signature": token["signature"],
        "trusted_time_claimed": token["trusted_time_claimed"],
        "time_source": token["time_source"],
        "claimed_time": token["claimed_time"],
        "target": token["target"],
        "token_kind": token["token_kind"],
        "token_id": token["token_id"],
        "timestamp_token_version": token["timestamp_token_version"],
    }
    assert canonical_timestamp_token_hash(token).ref == canonical_timestamp_token_hash(reordered).ref

    profile = load_fixture("profile_mock_local.json")
    assert canonical_timestamp_profile_hash(profile).ref == canonical_timestamp_profile_hash(
        dict(reversed(profile.items()))
    ).ref


def test_verify_binding_accepts_fixture_hash() -> None:
    assert verify_timestamp_token_binding(load_fixture("token_mock_bundle.json"), BUNDLE_HASH).ok
    assert not verify_timestamp_token_binding(load_fixture("token_mock_bundle.json"), MISMATCH_HASH).ok

from __future__ import annotations

from pathlib import Path

from klein.recording import (
    load_recorded_run_json,
    validate_raw_device_log_jsonl,
    validate_recorded_device_run,
    validate_recorded_run_package,
)

FIXTURES = Path("tests/fixtures/recorded_run")


def test_mock_recorded_run_package_validates() -> None:
    result = validate_recorded_run_package(FIXTURES / "mock_recorded_run")

    assert result.ok
    assert result.details["recorded_run_status"] == "pass"
    assert result.details["raw_log_status"] == "pass"


def test_recorded_run_rejects_hardware_claim_current_alpha() -> None:
    data = load_recorded_run_json(FIXTURES / "invalid_hardware_claim" / "recorded_run.json")
    result = validate_recorded_device_run(data)

    assert not result.ok
    assert result.error_code == "RECORDED_RUN_HARDWARE_CLAIM_UNSUPPORTED"


def test_recorded_run_rejects_attestation_current_alpha() -> None:
    data = load_recorded_run_json(FIXTURES / "invalid_attestation_claim" / "recorded_run.json")
    result = validate_recorded_device_run(data)

    assert not result.ok
    assert result.error_code == "RECORDED_RUN_ATTESTATION_UNSUPPORTED"


def test_raw_device_log_validates() -> None:
    result = validate_raw_device_log_jsonl(FIXTURES / "raw_device_log_valid.jsonl")

    assert result.ok
    assert result.details["event_count"] == 2


def test_raw_device_log_rejects_nonmonotonic_index() -> None:
    result = validate_raw_device_log_jsonl(FIXTURES / "invalid_raw_log_nonmonotonic.jsonl")

    assert not result.ok
    assert result.error_code == "RAW_DEVICE_LOG_ORDER_INVALID"


def test_raw_device_log_rejects_error_without_code() -> None:
    result = validate_raw_device_log_jsonl(FIXTURES / "invalid_raw_log_error_missing_code.jsonl")

    assert not result.ok
    assert result.error_code == "RAW_DEVICE_LOG_ERROR_CODE_MISSING"


def test_package_can_verify_inner_bundle_on_request() -> None:
    result = validate_recorded_run_package(FIXTURES / "mock_recorded_run", verify_bundle=True)

    assert result.ok
    assert result.details["bundle_verification_status"] == "pass"

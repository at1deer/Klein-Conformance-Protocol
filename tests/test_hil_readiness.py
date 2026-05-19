from __future__ import annotations

import json
from pathlib import Path

from klein.hil import MockHilBackend, validate_hil_backend_contract, validate_hil_backend_status
from klein.substrate.api import Frame

FIXTURES = Path("tests/fixtures/hil")


def _load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_valid_hil_contract_passes():
    result = validate_hil_backend_contract(_load("hil_contract_mock_dmf.json"))
    assert result.ok


def test_missing_emergency_stop_fails():
    result = validate_hil_backend_contract(_load("hil_contract_invalid_missing_estop.json"))
    assert not result.ok
    assert result.error_code == "HIL_ESTOP_REQUIRED"


def test_attestation_claim_fails_current_alpha():
    result = validate_hil_backend_contract(_load("hil_contract_invalid_claims_attestation.json"))
    assert not result.ok
    assert result.error_code == "HIL_ATTESTATION_UNSUPPORTED"


def test_status_unknown_ok_and_faulted_requires_error_code():
    assert validate_hil_backend_status(_load("hil_status_unknown.json")).ok
    assert validate_hil_backend_status(_load("hil_status_faulted.json")).ok
    result = validate_hil_backend_status(_load("hil_status_faulted_missing_error.json"))
    assert not result.ok
    assert result.error_code == "HIL_FAULT_MISSING_ERROR"


def test_mock_backend_health_estop_and_reset():
    backend = MockHilBackend()
    assert backend.get_health()["health"] == "UNKNOWN"
    backend.connect()
    assert backend.get_health()["health"] == "OK"
    backend.emergency_stop()
    ack = backend.apply_frame(Frame(seq=1, active_electrodes=(1,), duration_ms=10))
    assert not ack.ok
    assert backend.get_health()["emergency_stopped"] is True
    backend.reset()
    ack = backend.apply_frame(Frame(seq=2, active_electrodes=(1,), duration_ms=10))
    assert ack.ok


def test_mock_observation_is_not_physical_proof():
    backend = MockHilBackend()
    backend.apply_frame(Frame(seq=1, active_electrodes=(1, 2), duration_ms=10))
    observation = backend.read_observation()
    assert observation["source"]["source_type"] == "simulator"
    assert observation["metadata"]["hil_readiness_mock"] is True
    assert observation["metadata"]["physical_hardware"] is False

from __future__ import annotations

from pathlib import Path

from klein.backends.dmf import (
    GenericDmfDryRunAdapter,
    load_dmf_backend_adapter_config,
    validate_dmf_backend_adapter_config,
    validate_dmf_backend_adapter_status,
)
from klein.common.hashing import parse_ijson
from klein.execution import validate_execution_trace
from klein.execution.observation import validate_observation_snapshot
from klein.recording import validate_raw_device_log_jsonl, validate_recorded_run_package

FIXTURES = Path("tests/fixtures/backends/dmf")
RUNBOOK = Path("tests/fixtures/execution/runbook_minimal_dmf.json")
RECORDED = Path("tests/fixtures/recorded_run/dmf_dry_run_recorded_run")


def _load(path: Path) -> dict:
    data = parse_ijson(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_dmf_backend_adapter_config_and_status_validate() -> None:
    assert validate_dmf_backend_adapter_config(_load(FIXTURES / "generic_dmf_dry_run_config.json")).ok
    assert validate_dmf_backend_adapter_status(_load(FIXTURES / "generic_dmf_dry_run_status_unknown.json")).ok


def test_hardware_io_enabled_rejected() -> None:
    result = validate_dmf_backend_adapter_config(_load(FIXTURES / "generic_dmf_invalid_hardware_enabled.json"))
    assert not result.ok
    assert result.error_code == "DMF_ADAPTER_HARDWARE_IO_UNSUPPORTED"


def test_missing_estop_rejected() -> None:
    result = validate_dmf_backend_adapter_config(_load(FIXTURES / "generic_dmf_invalid_missing_estop.json"))
    assert not result.ok
    assert result.error_code == "DMF_ADAPTER_ESTOP_REQUIRED"


def test_invalid_profile_rejected() -> None:
    result = validate_dmf_backend_adapter_config(_load(FIXTURES / "generic_dmf_invalid_profile.json"))
    assert not result.ok
    assert result.error_code == "DMF_ADAPTER_PROFILE_UNSUPPORTED"


def test_dry_run_adapter_translates_runbook_to_trace_raw_log_and_observation(tmp_path: Path) -> None:
    adapter = GenericDmfDryRunAdapter(load_dmf_backend_adapter_config(FIXTURES / "generic_dmf_dry_run_config.json"))
    result = adapter.run_runbook_dry(_load(RUNBOOK), output_dir=tmp_path)

    assert result.ok
    assert len(result.trace["trace_steps"]) == 2
    assert validate_execution_trace(result.trace).ok
    assert validate_raw_device_log_jsonl(tmp_path / "raw" / "device-log.jsonl").ok
    assert result.observations
    assert validate_observation_snapshot(result.observations[0]).ok
    assert result.trace["metadata"]["dry_run"] is True


def test_emergency_stop_blocks_dry_run_and_reset_clears() -> None:
    adapter = GenericDmfDryRunAdapter(load_dmf_backend_adapter_config(FIXTURES / "generic_dmf_dry_run_config.json"))
    adapter.emergency_stop()
    blocked = adapter.run_runbook_dry(_load(RUNBOOK))
    assert not blocked.ok
    assert blocked.error_code == "DMF_ADAPTER_ESTOP_ACTIVE"
    adapter.reset()
    resumed = adapter.run_runbook_dry(_load(RUNBOOK))
    assert resumed.ok


def test_adapter_recorded_run_fixture_validates() -> None:
    assert validate_recorded_run_package(RECORDED).ok

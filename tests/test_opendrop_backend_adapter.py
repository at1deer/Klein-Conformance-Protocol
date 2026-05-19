from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

from klein.backends.dmf.opendrop import (
    OpenDropAdapterError,
    OpenDropEwodDryRunAdapter,
    build_electrode_mapping,
    serialize_intent_to_opendrop_command,
    serialize_intents_to_command_stream,
    validate_opendrop_adapter_config,
    validate_opendrop_adapter_status,
    validate_opendrop_command_intent,
    validate_opendrop_serial_command,
    validate_opendrop_transport_config,
)
from klein.common.hashing import parse_ijson
from klein.recording.validation import validate_recorded_run_package
from klein.tools.opendrop_backend import main as opendrop_cli_main

FIXTURES = Path("tests/fixtures/backends/dmf/opendrop")
SCHEMAS = Path("schemas/profiles/dmf")


def _load(path: str | Path) -> dict:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def _assert_schema_valid(schema_name: str, data: dict) -> None:
    schema = json.loads((SCHEMAS / schema_name).read_text(encoding="utf-8"))
    Draft7Validator(schema).validate(data)


def _assert_schema_invalid(schema_name: str, data: dict) -> None:
    with pytest.raises(JSONSchemaValidationError):
        _assert_schema_valid(schema_name, data)


def test_opendrop_config_and_status_validate() -> None:
    assert validate_opendrop_adapter_config(_load(FIXTURES / "opendrop_dry_run_config.json")).ok
    assert validate_opendrop_adapter_status(_load(FIXTURES / "opendrop_status_unknown.json")).ok


def test_opendrop_current_alpha_valid_fixtures_pass_schema() -> None:
    _assert_schema_valid("opendrop_adapter_config.schema.json", _load(FIXTURES / "opendrop_dry_run_config.json"))
    _assert_schema_valid("opendrop_adapter_status.schema.json", _load(FIXTURES / "opendrop_status_unknown.json"))
    _assert_schema_valid("opendrop_transport_config.schema.json", _load(FIXTURES / "opendrop_transport_none.json"))
    _assert_schema_valid("opendrop_transport_config.schema.json", _load(FIXTURES / "opendrop_transport_serial_experimental_disabled.json"))
    _assert_schema_valid("opendrop_serial_command.schema.json", _load(FIXTURES / "serial_command_set_electrodes.json"))


@pytest.mark.parametrize(
    ("schema_name", "fixture"),
    [
        ("opendrop_adapter_config.schema.json", "opendrop_invalid_hardware_enabled.json"),
        ("opendrop_adapter_config.schema.json", "opendrop_invalid_transport_serial.json"),
        ("opendrop_adapter_config.schema.json", "opendrop_invalid_missing_estop.json"),
        ("opendrop_transport_config.schema.json", "opendrop_transport_invalid_hardware_enabled.json"),
        ("opendrop_transport_config.schema.json", "opendrop_transport_invalid_endpoint_current_alpha.json"),
        ("opendrop_serial_command.schema.json", "serial_command_invalid_hardware_allowed.json"),
    ],
)
def test_opendrop_current_alpha_invalid_fixtures_fail_schema(schema_name: str, fixture: str) -> None:
    _assert_schema_invalid(schema_name, _load(FIXTURES / fixture))


def test_opendrop_status_connected_or_hardware_enabled_fails_schema() -> None:
    status = _load(FIXTURES / "opendrop_status_unknown.json")
    status["connected"] = True
    _assert_schema_invalid("opendrop_adapter_status.schema.json", status)

    status = _load(FIXTURES / "opendrop_status_unknown.json")
    status["hardware_io_enabled"] = True
    _assert_schema_invalid("opendrop_adapter_status.schema.json", status)

    status = _load(FIXTURES / "opendrop_status_unknown.json")
    status["transport_status"] = "CONNECTED"
    _assert_schema_invalid("opendrop_adapter_status.schema.json", status)


@pytest.mark.parametrize(
    ("fixture", "error_code"),
    [
        ("opendrop_invalid_hardware_enabled.json", "OPENDROP_HARDWARE_IO_UNSUPPORTED"),
        ("opendrop_invalid_transport_serial.json", "OPENDROP_TRANSPORT_UNSUPPORTED"),
        ("opendrop_invalid_missing_estop.json", "DMF_ADAPTER_ESTOP_REQUIRED"),
        ("opendrop_invalid_duplicate_mapping.json", "OPENDROP_MAPPING_DUPLICATE"),
    ],
)
def test_opendrop_invalid_configs_fail(fixture: str, error_code: str) -> None:
    result = validate_opendrop_adapter_config(_load(FIXTURES / fixture))
    assert not result.ok
    assert result.error_code == error_code


def test_row_major_mapping_coordinates() -> None:
    mapping = build_electrode_mapping(_load(FIXTURES / "opendrop_dry_run_config.json"))
    assert mapping[1].electrode_id == "E0001"
    assert (mapping[1].x, mapping[1].y) == (0, 0)
    assert mapping[2].electrode_id == "E0002"
    assert (mapping[2].x, mapping[2].y) == (1, 0)
    assert mapping[128].electrode_id == "E0128"
    assert (mapping[128].x, mapping[128].y) == (15, 7)


def test_command_intent_validation_and_oob() -> None:
    assert validate_opendrop_command_intent(_load(FIXTURES / "command_intent_channel_list.json"), channel_count=128).ok
    assert validate_opendrop_command_intent(_load(FIXTURES / "command_intent_sparse_frame.json"), channel_count=128).ok
    result = validate_opendrop_command_intent(_load(FIXTURES / "command_intent_invalid_oob_channel.json"), channel_count=128)
    assert not result.ok
    assert result.error_code == "OPENDROP_CHANNEL_OOB"


def test_opendrop_transport_planning_configs_validate() -> None:
    assert validate_opendrop_transport_config(_load(FIXTURES / "opendrop_transport_none.json")).ok
    assert validate_opendrop_transport_config(_load(FIXTURES / "opendrop_transport_serial_experimental_disabled.json")).ok


@pytest.mark.parametrize(
    ("fixture", "error_code"),
    [
        ("opendrop_transport_invalid_hardware_enabled.json", "OPENDROP_HARDWARE_IO_UNSUPPORTED"),
        ("opendrop_transport_invalid_endpoint_current_alpha.json", "OPENDROP_ENDPOINT_UNSUPPORTED_CURRENT_ALPHA"),
    ],
)
def test_opendrop_transport_current_alpha_rejections(fixture: str, error_code: str) -> None:
    result = validate_opendrop_transport_config(_load(FIXTURES / fixture))
    assert not result.ok
    assert result.error_code == error_code


def test_opendrop_serial_commands_validate() -> None:
    assert validate_opendrop_serial_command(_load(FIXTURES / "serial_command_set_electrodes.json")).ok
    assert validate_opendrop_serial_command(_load(FIXTURES / "serial_command_apply_frame.json")).ok
    result = validate_opendrop_serial_command(_load(FIXTURES / "serial_command_invalid_hardware_allowed.json"))
    assert not result.ok
    assert result.error_code == "OPENDROP_HARDWARE_IO_UNSUPPORTED"


def test_opendrop_intent_serialization_is_deterministic() -> None:
    transport = _load(FIXTURES / "opendrop_transport_none.json")
    intent = _load(FIXTURES / "command_intent_channel_list.json")
    command = serialize_intent_to_opendrop_command(intent, transport)
    assert command == _load(FIXTURES / "serial_command_set_electrodes.json")
    assert command["tick"] == intent["tick"]
    assert command["payload"]["electrodes"][0]["channel_id"] == 1
    assert command["payload"]["electrodes"][0]["state"] == "ON"
    assert command["payload"]["electrodes"][0]["voltage_v"] == 120
    assert command["payload"]["electrodes"][0]["frequency_hz"] == 1000
    json.loads(command["raw_line"])


def test_opendrop_command_stream_fixture_matches_serialization() -> None:
    transport = _load(FIXTURES / "opendrop_transport_none.json")
    intents = [_load(FIXTURES / "command_intent_channel_list.json"), _load(FIXTURES / "command_intent_sparse_frame.json")]
    expected = (FIXTURES / "command_stream_minimal.jsonl").read_text(encoding="utf-8")
    assert serialize_intents_to_command_stream(intents, transport) == expected
    assert [json.loads(line) for line in expected.splitlines()]


def test_opendrop_cli_serialize_runbook_creates_command_stream(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    output = tmp_path / "opendrop_commands.jsonl"
    exit_code = opendrop_cli_main([
        "serialize-runbook",
        "--config",
        str(FIXTURES / "opendrop_dry_run_config.json"),
        "--transport",
        str(FIXTURES / "opendrop_transport_none.json"),
        "--runbook",
        "tests/fixtures/execution/runbook_minimal_dmf.json",
        "--output",
        str(output),
    ])
    assert exit_code == 0
    stdout = capsys.readouterr().out
    assert "serialized command stream only" in stdout
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["hardware_io_allowed"] is False
    assert rows[0]["payload"]["electrodes"][0]["channel_id"] == 1
    assert rows[1]["payload"]["electrodes"][0]["channel_id"] == 2


def test_runbook_generates_opendrop_intents_and_mock_observations(tmp_path: Path) -> None:
    adapter = OpenDropEwodDryRunAdapter(_load(FIXTURES / "opendrop_dry_run_config.json"))
    runbook = _load("tests/fixtures/execution/runbook_minimal_dmf.json")
    result = adapter.run_runbook_dry(runbook, output_dir=tmp_path)
    assert result.ok
    assert result.trace["run_id"] == "opendrop-ewod-dry-run"
    assert result.trace["trace_steps"][0]["details"]["adapter_command"] == "SET_ELECTRODES"
    assert result.trace["trace_steps"][0]["details"]["electrode_ids"] == ["E0001"]
    assert result.observations[0]["metadata"]["physical_hardware"] is False
    raw_log = (tmp_path / "raw" / "device-log.jsonl").read_text(encoding="utf-8")
    assert "OPENDROP_SET_ELECTRODES" in raw_log
    assert "serial_command" in raw_log
    assert "OPENDROP_READ_MOCK_OBSERVATION" in raw_log


def test_emergency_stop_blocks_dry_run() -> None:
    adapter = OpenDropEwodDryRunAdapter(_load(FIXTURES / "opendrop_dry_run_config.json"))
    adapter.emergency_stop()
    result = adapter.run_runbook_dry(_load("tests/fixtures/execution/runbook_minimal_dmf.json"))
    assert not result.ok
    assert result.error_code == "DMF_ADAPTER_ESTOP_ACTIVE"


def test_unsupported_frame_format_fails_explicitly() -> None:
    adapter = OpenDropEwodDryRunAdapter(_load(FIXTURES / "opendrop_dry_run_config.json"))
    runbook = _load("tests/fixtures/execution/runbook_minimal_dmf.json")
    runbook["planned_steps"][0]["expected_effect"]["details"] = {"frame_format": "rle"}
    with pytest.raises(OpenDropAdapterError) as excinfo:
        adapter.run_runbook_dry(runbook)
    assert excinfo.value.error_code == "OPENDROP_COMMAND_INTENT_INVALID"


def test_recorded_run_package_generated_by_opendrop_adapter(tmp_path: Path) -> None:
    adapter = OpenDropEwodDryRunAdapter(_load(FIXTURES / "opendrop_dry_run_config.json"))
    result = adapter.run_runbook_dry(_load("tests/fixtures/execution/runbook_minimal_dmf.json"))
    out = adapter.create_recorded_run_from_adapter_result(
        result,
        bundle_path="tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun",
        output_dir=tmp_path,
    )
    assert validate_recorded_run_package(out).ok
    recorded = json.loads((out / "recorded_run.json").read_text(encoding="utf-8"))
    assert recorded["source_type"] == "mock_hardware"
    assert recorded["hardware_claimed"] is False
    assert recorded["attestation"] is None
    assert (out / "backend" / "opendrop_adapter_config.json").exists()


def test_explicit_mapping_duplicate_raises() -> None:
    with pytest.raises(OpenDropAdapterError) as excinfo:
        OpenDropEwodDryRunAdapter(_load(FIXTURES / "opendrop_invalid_duplicate_mapping.json"))
    assert excinfo.value.error_code == "OPENDROP_MAPPING_DUPLICATE"

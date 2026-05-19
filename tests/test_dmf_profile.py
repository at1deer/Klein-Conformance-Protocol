from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

from klein.common.errors import ErrorCode
from klein.crypto.capabilities import (
    BackendCapabilityError,
    validate_backend_capability_declaration,
)
from klein.profiles.dmf import (
    DMFProfileContext,
    build_dmf_profile_context,
    hash_substrate_fingerprint,
    validate_dmf_capabilities,
)
from klein.profiles.dmf.validation import (
    validate_dmf_frame,
    validate_dmf_payload,
    validate_dmf_payload_result,
)
from klein.sim.virtual_substrate import VirtualSubstrate

FIXTURES = Path("tests/fixtures/profiles/dmf")
CAPABILITY_DECLARATION = Path("tests/fixtures/capabilities/full_simulator_dmf_capabilities_signed.json")
SCHEMAS = Path("schemas/profiles/dmf")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _schema(name: str) -> dict:
    return _load(SCHEMAS / name)


def test_dmf_schemas_parse_and_valid_fixtures_pass() -> None:
    Draft7Validator(_schema("dmf_capabilities.schema.json")).validate(
        _load(FIXTURES / "capabilities_valid.json")
    )
    Draft7Validator(_schema("dmf_payload.schema.json")).validate(
        _load(FIXTURES / "payload_channel_list_valid.json")
    )
    Draft7Validator(_schema("dmf_frame.schema.json")).validate(
        _load(FIXTURES / "payload_frame_sequence_sparse_valid.json")["data"][0]
    )


def test_dmf_schema_rejects_invalid_ranges_shape_and_rle() -> None:
    with pytest.raises(JSONSchemaValidationError):
        Draft7Validator(_schema("dmf_capabilities.schema.json")).validate(
            _load(FIXTURES / "capabilities_missing_substrate.json")
        )
    with pytest.raises(JSONSchemaValidationError):
        Draft7Validator(_schema("dmf_payload.schema.json")).validate(
            _load(FIXTURES / "payload_frame_sequence_rle_unsupported.json")
        )


def test_dmf_runtime_rejects_invalid_ranges_and_conflicts() -> None:
    invalid = validate_dmf_capabilities(_load(FIXTURES / "capabilities_invalid_ranges.json"))
    assert not invalid.ok
    assert invalid.error_code == ErrorCode.DMF_CAPABILITIES_INVALID

    context = validate_dmf_capabilities(_load(FIXTURES / "capabilities_valid.json")).context
    assert context is not None
    errors = validate_dmf_payload(_load(FIXTURES / "payload_channel_list_conflict.json"), context)
    assert errors[0].code == ErrorCode.PAYLOAD_CONFLICTING_STATE


def test_dmf_runtime_validates_frame_and_payload_result_objects() -> None:
    context = DMFProfileContext(max_channels=16, grid_width=4, grid_height=4)

    payload_result = validate_dmf_payload_result(
        _load(FIXTURES / "payload_frame_sequence_delta_tiles_valid.json"),
        context,
    )
    assert payload_result.ok

    frame_result = validate_dmf_frame({"t": 0, "format": "sparse", "data": [{"x": 5, "y": 0}]}, context)
    assert not frame_result.ok
    assert frame_result.errors[0].code == ErrorCode.PAYLOAD_OOB_PIXEL


def test_channel_list_conversion_sorts_ticks_and_preserves_off_state() -> None:
    from klein.profiles.dmf.payload import PayloadParser

    parser = PayloadParser()
    sequence = parser.parse_container_payload({
        "kind": "CHANNEL_LIST",
        "data": [
            {"t": 2, "channel_id": 8, "state": "ON", "voltage_v": 100.0},
            {"t": 0, "channel_id": 5, "state": "ON", "voltage_v": 100.0},
            {"t": 1, "channel_id": 5, "state": "OFF", "voltage_v": 0.0},
            {"t": 1, "channel_id": 6, "state": "ON", "voltage_v": 100.0},
        ],
    })

    assert [frame.tags["tick"] for frame in sequence.frames] == [0, 1, 2]
    assert sequence.frames[1].active_electrodes == (6,)


def test_profile_validation_rejects_oob_voltage_frequency_and_bitmap_dimensions() -> None:
    context = DMFProfileContext(max_channels=8, grid_width=4, grid_height=2)

    voltage_errors = validate_dmf_payload(
        {"kind": "CHANNEL_LIST", "data": [{"t": 0, "channel_id": 1, "state": "ON", "voltage_v": 400.0}]},
        context,
    )
    assert voltage_errors[0].code == ErrorCode.PAYLOAD_VOLTAGE_OOB

    frequency_errors = validate_dmf_payload(
        {
            "kind": "CHANNEL_LIST",
            "data": [{"t": 0, "channel_id": 1, "state": "ON", "voltage_v": 100.0, "frequency_hz": 100000.0}],
        },
        context,
    )
    assert frequency_errors[0].code == ErrorCode.PAYLOAD_FREQUENCY_OOB

    bitmap_errors = validate_dmf_payload({"kind": "BITMAP_SEQUENCE", "data": ["//8="]}, context)
    assert bitmap_errors[0].code == ErrorCode.PAYLOAD_UNSUPPORTED_DIMS


def test_profile_validation_rejects_sparse_duplicate_delta_missing_and_rle() -> None:
    context = DMFProfileContext(max_channels=16, grid_width=4, grid_height=4)

    duplicate = validate_dmf_payload(
        {"kind": "FRAME_SEQUENCE", "data": [{"t": 0, "format": "sparse", "data": [1, 1]}]},
        context,
    )
    assert duplicate[0].code == ErrorCode.PAYLOAD_DUPLICATE_PIXEL

    delta_conflict = validate_dmf_payload(
        {
            "kind": "FRAME_SEQUENCE",
            "data": [{"t": 0, "format": "delta_tiles", "data": {"add": [1], "remove": [1]}}],
        },
        context,
    )
    assert delta_conflict[0].code == ErrorCode.PAYLOAD_DELTA_CONFLICT

    delta_missing = validate_dmf_payload(
        {
            "kind": "FRAME_SEQUENCE",
            "data": [{"t": 0, "format": "delta_tiles", "data": {"add": [], "remove": [1]}}],
        },
        context,
    )
    assert delta_missing[0].code == ErrorCode.PAYLOAD_DELTA_REMOVE_MISS

    rle = validate_dmf_payload(
        {"kind": "FRAME_SEQUENCE", "data": [{"t": 0, "format": "rle", "data": [1]}]},
        context,
    )
    assert rle[0].code == ErrorCode.PAYLOAD_UNSUPPORTED_FRAME_FORMAT


def test_dmf_context_derives_bounds_and_payload_can_fail_under_another_context() -> None:
    capabilities = _load(FIXTURES / "capabilities_valid.json")
    context = build_dmf_profile_context(capabilities)

    assert context.max_channels == 128
    assert context.grid_width == 16
    assert context.grid_height == 8
    assert context.voltage_max_v == 300.0

    payload = _load(FIXTURES / "payload_channel_list_valid.json")
    assert validate_dmf_payload(payload, context) == []
    smaller = DMFProfileContext(max_channels=1, grid_width=1, grid_height=1)
    assert validate_dmf_payload(payload, smaller)[0].code == ErrorCode.PAYLOAD_CHANNEL_OOB


def test_substrate_fingerprint_changes_with_context_shape() -> None:
    first = VirtualSubstrate(max_channels=16, grid_width=4, grid_height=4)
    second = VirtualSubstrate(max_channels=16, grid_width=8, grid_height=2)
    first.connect("virtual://first")
    second.connect("virtual://second")

    assert hash_substrate_fingerprint(first.get_capabilities(), first.get_topology()).ref != (
        hash_substrate_fingerprint(second.get_capabilities(), second.get_topology()).ref
    )


def test_backend_capability_declaration_enforces_dmf_schema() -> None:
    declaration = _load(CAPABILITY_DECLARATION)
    validate_backend_capability_declaration(declaration)

    missing = json.loads(json.dumps(declaration))
    del missing["payload"]["profile_capabilities"]["dmf"]
    with pytest.raises(BackendCapabilityError) as exc_info:
        validate_backend_capability_declaration(missing)
    assert exc_info.value.error_code == "DMF_CAPABILITIES_INVALID"

    unsupported = json.loads(json.dumps(declaration))
    unsupported["payload"]["profile_capabilities"]["dmf"]["payloads"]["supported_payload_kinds"].append("RLE")
    with pytest.raises(BackendCapabilityError) as exc_info:
        validate_backend_capability_declaration(unsupported)
    assert exc_info.value.error_code == "DMF_CAPABILITIES_INVALID"

    no_substrate = json.loads(json.dumps(declaration))
    no_substrate["payload"]["substrates"] = []
    with pytest.raises(BackendCapabilityError) as exc_info:
        validate_backend_capability_declaration(no_substrate)
    assert exc_info.value.error_code == "DMF_SUBSTRATE_MISMATCH"

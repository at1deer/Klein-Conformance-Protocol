from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

from klein.common.errors import ErrorCode
from klein.profiles.dmf import DMFProfileContext, validate_dmf_capabilities
from klein.profiles.dmf.validation import validate_dmf_payload

FIXTURES = Path("tests/fixtures/profiles/dmf")
SCHEMAS = Path("schemas/profiles/dmf")
CONTEXT = DMFProfileContext(max_channels=128, grid_width=16, grid_height=8)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema_name: str) -> Draft7Validator:
    return Draft7Validator(_load(SCHEMAS / schema_name))


def test_valid_capabilities_pass_schema_and_python_validator() -> None:
    capabilities = _load(FIXTURES / "capabilities_valid.json")

    _validator("dmf_capabilities.schema.json").validate(capabilities)
    assert validate_dmf_capabilities(capabilities).ok


def test_invalid_ranges_fail_python_validator_even_when_shape_is_valid() -> None:
    capabilities = _load(FIXTURES / "capabilities_invalid_ranges.json")

    _validator("dmf_capabilities.schema.json").validate(capabilities)
    result = validate_dmf_capabilities(capabilities)
    assert not result.ok
    assert result.error_code == ErrorCode.DMF_CAPABILITIES_INVALID


def test_channel_list_schema_and_runtime_parity() -> None:
    valid = _load(FIXTURES / "payload_channel_list_valid.json")
    invalid_shape = _load(FIXTURES / "payload_channel_list_invalid_shape.json")

    _validator("dmf_payload.schema.json").validate(valid)
    assert validate_dmf_payload(valid, CONTEXT) == []
    with pytest.raises(JSONSchemaValidationError):
        _validator("dmf_payload.schema.json").validate(invalid_shape)


def test_sparse_frame_schema_and_runtime_parity() -> None:
    valid = _load(FIXTURES / "payload_frame_sequence_sparse_valid.json")
    oob = _load(FIXTURES / "payload_frame_sequence_sparse_oob.json")

    _validator("dmf_payload.schema.json").validate(valid)
    assert validate_dmf_payload(valid, CONTEXT) == []
    _validator("dmf_payload.schema.json").validate(oob)
    assert validate_dmf_payload(oob, CONTEXT)[0].code == ErrorCode.PAYLOAD_OOB_PIXEL


def test_bitmap_shape_schema_and_runtime_base64_parity() -> None:
    valid = _load(FIXTURES / "payload_bitmap_valid.json")
    invalid_shape = _load(FIXTURES / "payload_bitmap_invalid_shape.json")
    invalid_base64 = _load(FIXTURES / "payload_bitmap_invalid_base64.json")

    _validator("dmf_payload.schema.json").validate(valid)
    assert validate_dmf_payload(valid, CONTEXT) == []
    with pytest.raises(JSONSchemaValidationError):
        _validator("dmf_payload.schema.json").validate(invalid_shape)
    _validator("dmf_payload.schema.json").validate(invalid_base64)
    assert validate_dmf_payload(invalid_base64, CONTEXT)[0].code == ErrorCode.PAYLOAD_BASE64_INVALID


def test_rle_is_rejected_by_schema_and_runtime() -> None:
    rle = _load(FIXTURES / "payload_frame_sequence_rle_unsupported.json")

    with pytest.raises(JSONSchemaValidationError):
        _validator("dmf_payload.schema.json").validate(rle)
    assert validate_dmf_payload(rle, CONTEXT)[0].code == ErrorCode.PAYLOAD_UNSUPPORTED_FRAME_FORMAT

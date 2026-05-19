from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError

from klein.artifacts import canonical_artifact_hash, validate_artifact
from klein.common.hashing import raw_file_sha256
from klein.tools.artifact import main as artifact_main

FIXTURES = Path("tests/fixtures/artifacts")
SCHEMAS = Path("schemas")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validator(schema_name: str) -> Draft7Validator:
    return Draft7Validator(_load(SCHEMAS / schema_name))


def test_valid_project_passes_schema_and_runtime_validator() -> None:
    project = _load(FIXTURES / "project_minimal_valid.klein")

    _validator("klein_project.schema.json").validate(project)
    result = validate_artifact(project)
    assert result.ok
    assert result.artifact_type == "project"
    assert result.profile_id == "dmf"


def test_valid_container_passes_schema_and_runtime_validator() -> None:
    container = _load(FIXTURES / "container_minimal_valid.kleinc")

    _validator("klein_container.schema.json").validate(container)
    result = validate_artifact(container)
    assert result.ok
    assert result.artifact_type == "container"
    assert result.profile_id == "dmf"


def test_missing_profile_and_missing_payload_fail_schema_or_runtime() -> None:
    project = _load(FIXTURES / "project_invalid_missing_profile.klein")
    container = _load(FIXTURES / "container_invalid_missing_profile.kleinc")

    with pytest.raises(JSONSchemaValidationError):
        _validator("klein_project.schema.json").validate(project)
    assert validate_artifact(project).error_code == "ARTIFACT_PROFILE_MISSING"

    with pytest.raises(JSONSchemaValidationError):
        _validator("klein_container.schema.json").validate(container)
    assert validate_artifact(container).error_code == "ARTIFACT_PAYLOAD_MISSING"


def test_invalid_payload_shape_fails_runtime_profile_validation() -> None:
    project = _load(FIXTURES / "project_invalid_payload.klein")
    container = _load(FIXTURES / "container_invalid_payload.kleinc")

    _validator("klein_project.schema.json").validate(project)
    _validator("klein_container.schema.json").validate(container)
    assert validate_artifact(project).error_code == "PAYLOAD_MALFORMED"
    assert validate_artifact(container).error_code == "PAYLOAD_MALFORMED"


def test_artifact_canonical_hash_stable_under_key_ordering() -> None:
    project_hash = canonical_artifact_hash(FIXTURES / "project_minimal_valid.klein")
    reordered_project_hash = canonical_artifact_hash(FIXTURES / "project_reordered_equivalent.klein")
    container_hash = canonical_artifact_hash(FIXTURES / "container_minimal_valid.kleinc")
    reordered_container_hash = canonical_artifact_hash(FIXTURES / "container_reordered_equivalent.kleinc")

    assert project_hash.ref == reordered_project_hash.ref
    assert container_hash.ref == reordered_container_hash.ref
    assert project_hash.canonicalization == "klein.canon.json.v1"
    assert container_hash.canonicalization == "klein.canon.json.v1"


def test_artifact_hash_changes_when_payload_changes(tmp_path: Path) -> None:
    first = _load(FIXTURES / "project_minimal_valid.klein")
    second = json.loads(json.dumps(first))
    second["payload"]["data"] = [{"t": 0, "channel_id": 1, "state": "ON", "voltage_v": 100.0}]
    first_path = tmp_path / "first.klein"
    second_path = tmp_path / "second.klein"
    first_path.write_text(json.dumps(first), encoding="utf-8")
    second_path.write_text(json.dumps(second), encoding="utf-8")

    assert canonical_artifact_hash(first_path).ref != canonical_artifact_hash(second_path).ref


def test_malformed_artifact_has_raw_hash_but_no_canonical_hash(tmp_path: Path) -> None:
    bad = tmp_path / "bad.kleinc"
    bad.write_text('{"not": ', encoding="utf-8")

    assert raw_file_sha256(bad).ref.startswith("sha256:")
    with pytest.raises(ValueError):
        canonical_artifact_hash(bad)


def test_klein_artifact_cli_validate_and_hash(capsys: pytest.CaptureFixture[str]) -> None:
    assert artifact_main(["validate", str(FIXTURES / "project_minimal_valid.klein")]) == 0
    assert "Artifact valid: type=project" in capsys.readouterr().out

    assert artifact_main(["hash", str(FIXTURES / "container_minimal_valid.kleinc")]) == 0
    assert capsys.readouterr().out.strip().startswith("sha256:")

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest
from jsonschema import Draft7Validator

from klein.crypto.manifest import load_run_manifest
from klein.crypto.registry import (
    BackendIdentityRegistryError,
    load_backend_identity_registry,
    resolve_manifest_backend_identity,
    validate_backend_identity_registry,
)

REGISTRY_PATH = Path("tests/fixtures/crypto/backend_registry_test.json")
MANIFEST_PATH = Path("tests/fixtures/signed_conformance/manifest_signed.json")


def _registry() -> dict:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def _manifest() -> dict:
    return load_run_manifest(MANIFEST_PATH)


def test_backend_identity_registry_validates_against_schema() -> None:
    registry = _registry()
    schema = json.loads(Path("schemas/backend_identity_registry.schema.json").read_text())

    loaded = validate_backend_identity_registry(registry)

    assert loaded.registry_id == "klein-test-registry"
    Draft7Validator(schema).validate(registry)


@pytest.mark.parametrize(
    ("mutate", "code"),
    [
        (lambda data: data["backends"].append(deepcopy(data["backends"][0])), "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID"),
        (lambda data: data["backends"][0]["keys"].append(deepcopy(data["backends"][0]["keys"][0])), "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID"),
        (lambda data: data["backends"][0]["keys"][0].update(public_key="bad"), "BACKEND_IDENTITY_REGISTRY_SCHEMA_INVALID"),
    ],
)
def test_backend_identity_registry_schema_failures(mutate, code: str) -> None:
    registry = _registry()
    mutate(registry)

    with pytest.raises(BackendIdentityRegistryError) as exc:
        validate_backend_identity_registry(registry)

    assert exc.value.error_code == code


@pytest.mark.parametrize(
    ("mutate_manifest", "mutate_registry", "code"),
    [
        (lambda manifest: manifest["payload"].update(backend_id="missing"), None, "BACKEND_IDENTITY_NOT_FOUND"),
        (None, lambda registry: registry["backends"][0]["keys"][0].update(key_id="other"), "BACKEND_IDENTITY_KEY_NOT_FOUND"),
        (lambda manifest: manifest["signatures"][0].update(public_key="A" * 43 + "="), None, "BACKEND_IDENTITY_KEY_MISMATCH"),
        (None, lambda registry: registry["backends"][0]["keys"][0].update(status="revoked"), "BACKEND_IDENTITY_KEY_REVOKED"),
        (lambda manifest: manifest["payload"].update(backend_version="9.9.9"), None, "BACKEND_IDENTITY_SCOPE_MISMATCH"),
        (lambda manifest: manifest["payload"].update(profile_id="other"), None, "BACKEND_IDENTITY_SCOPE_MISMATCH"),
    ],
)
def test_manifest_backend_identity_resolution_failures(mutate_manifest, mutate_registry, code: str) -> None:
    manifest = _manifest()
    registry = _registry()
    if mutate_manifest is not None:
        mutate_manifest(manifest)
    if mutate_registry is not None:
        mutate_registry(registry)

    result = resolve_manifest_backend_identity(manifest["payload"], manifest["signatures"][0], registry)

    assert not result.ok
    assert result.error_code == code


def test_backend_identity_registry_loads_from_path() -> None:
    assert load_backend_identity_registry(REGISTRY_PATH).registry_id == "klein-test-registry"

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from klein.crypto.manifest import load_run_manifest, verify_run_manifest
from klein.crypto.registry import (
    load_backend_identity_registry,
    resolve_backend_identity,
    verify_backend_registry_signature,
)
from klein.crypto.trust import load_trust_policy

REGISTRY = Path("tests/fixtures/crypto/backend_registry_signed_test.json")
UNSIGNED_REGISTRY = Path("tests/fixtures/crypto/backend_registry_test.json")
TAMPERED_REGISTRY = Path("tests/fixtures/crypto/backend_registry_signed_tampered.json")
UNTRUSTED_REGISTRY = Path("tests/fixtures/crypto/backend_registry_signed_untrusted.json")
REVOKED_REGISTRY = Path("tests/fixtures/crypto/backend_registry_signed_revoked_key.json")
RETIRED_REGISTRY = Path("tests/fixtures/crypto/backend_registry_signed_retired_key.json")
POLICY = Path("tests/fixtures/crypto/trust_policy_registry_authority_test.json")
WRONG_SCOPE_POLICY = Path("tests/fixtures/crypto/trust_policy_registry_authority_wrong_scope.json")
MANIFEST = Path("tests/fixtures/signed_conformance/manifest_signed.json")


def _manifest() -> dict:
    return load_run_manifest(MANIFEST)


def test_signed_registry_verifies_with_trusted_authority() -> None:
    registry = load_backend_identity_registry(REGISTRY)
    policy = load_trust_policy(POLICY)

    result = verify_backend_registry_signature(registry, trust_policy=policy)

    assert result.registry_signed is True
    assert result.registry_signature_status == "valid"
    assert result.registry_provenance_status == "trusted"
    assert result.registry_authority_id == "klein-test-registry-root"


def test_signed_registry_valid_without_authority_is_not_evaluated() -> None:
    result = verify_backend_registry_signature(load_backend_identity_registry(REGISTRY))

    assert result.registry_signature_status == "valid"
    assert result.registry_provenance_status == "not_evaluated"


def test_signed_registry_wrong_authority_scope_is_untrusted_when_required() -> None:
    result = verify_backend_registry_signature(
        load_backend_identity_registry(REGISTRY),
        trust_policy=load_trust_policy(WRONG_SCOPE_POLICY),
        require_trusted=True,
    )

    assert result.registry_signature_status == "valid"
    assert result.registry_provenance_status == "untrusted"
    assert result.registry_error_code == "BACKEND_REGISTRY_AUTHORITY_UNTRUSTED"


def test_signed_registry_tampering_invalidates_signature() -> None:
    result = verify_backend_registry_signature(load_backend_identity_registry(TAMPERED_REGISTRY))

    assert result.registry_signature_status == "invalid"
    assert result.registry_error_code == "BACKEND_REGISTRY_SIGNATURE_INVALID"


def test_unsigned_registry_allowed_without_strict_provenance() -> None:
    result = verify_backend_registry_signature(load_backend_identity_registry(UNSIGNED_REGISTRY))

    assert result.registry_signed is False
    assert result.registry_signature_status == "not_applicable"
    assert result.registry_provenance_status == "not_evaluated"


def test_unsigned_registry_fails_when_provenance_required() -> None:
    result = verify_backend_registry_signature(
        load_backend_identity_registry(UNSIGNED_REGISTRY),
        trust_policy=load_trust_policy(POLICY),
        require_trusted=True,
    )

    assert result.registry_signature_status == "missing"
    assert result.registry_error_code == "BACKEND_REGISTRY_PROVENANCE_REQUIRED"


def test_registry_backed_manifest_reports_trusted_provenance() -> None:
    result = verify_run_manifest(
        _manifest(),
        trust_policy=load_trust_policy(POLICY),
        backend_registry=load_backend_identity_registry(REGISTRY),
        require_registry_provenance=True,
    )

    assert result.ok
    assert result.registry_signature_status == "valid"
    assert result.registry_provenance_status == "trusted"
    assert result.key_lifecycle_status == "active"


def test_registry_revoked_key_fails_identity_resolution() -> None:
    result = verify_run_manifest(
        _manifest(),
        trust_policy=load_trust_policy(POLICY),
        backend_registry=load_backend_identity_registry(REVOKED_REGISTRY),
        require_registry_provenance=True,
    )

    assert not result.ok
    assert result.error_code == "BACKEND_IDENTITY_KEY_REVOKED"
    assert result.key_lifecycle_status == "revoked"


def test_retired_key_without_created_at_is_untrusted() -> None:
    result = verify_run_manifest(
        _manifest(),
        trust_policy=load_trust_policy(POLICY),
        backend_registry=load_backend_identity_registry(RETIRED_REGISTRY),
        require_registry_provenance=True,
    )

    assert not result.ok
    assert result.error_code == "BACKEND_IDENTITY_KEY_RETIRED"
    assert result.key_lifecycle_status == "indeterminate"


def test_retired_key_with_created_at_inside_window_is_legacy_valid() -> None:
    manifest = deepcopy(_manifest())
    manifest["payload"]["created_at"] = "2026-05-15T00:00:00Z"

    result = resolve_backend_identity(
        manifest["payload"],
        manifest["signatures"][0],
        load_backend_identity_registry(RETIRED_REGISTRY),
        trust_policy=load_trust_policy(POLICY),
        require_registry_provenance=True,
    )

    assert result.ok
    assert result.key_lifecycle_status == "legacy_valid"


def test_not_before_not_after_are_enforced() -> None:
    registry = json.loads(UNSIGNED_REGISTRY.read_text(encoding="utf-8"))
    registry["backends"][0]["keys"][0]["not_before"] = "2027-01-01T00:00:00Z"

    resolution = resolve_backend_identity(
        _manifest()["payload"] | {"created_at": "2026-05-15T00:00:00Z"},
        _manifest()["signatures"][0],
        registry,
    )

    assert not resolution.ok
    assert resolution.error_code == "BACKEND_IDENTITY_KEY_NOT_YET_VALID"

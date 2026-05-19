from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from klein.crypto.manifest import load_run_manifest, verify_run_manifest
from klein.crypto.registry import load_backend_identity_registry
from klein.crypto.trust import TrustPolicyError, load_trust_policy

MANIFEST = Path("tests/fixtures/signed_conformance/manifest_signed.json")
SELF_CONTAINED_POLICY = Path("tests/fixtures/signed_conformance/trust_policy.json")
REGISTRY_POLICY = Path("tests/fixtures/crypto/trust_policy_registry_backed.json")
REGISTRY = Path("tests/fixtures/crypto/backend_registry_test.json")


def _manifest() -> dict:
    return load_run_manifest(MANIFEST)


def _policy(path: Path = REGISTRY_POLICY) -> dict:
    return load_trust_policy(path)


def _registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def test_self_contained_trust_policy_still_works() -> None:
    result = verify_run_manifest(_manifest(), trust_policy=load_trust_policy(SELF_CONTAINED_POLICY))

    assert result.ok
    assert result.trust_status == "trusted"
    assert result.identity_status == "not_evaluated"


def test_registry_backed_trust_policy_works() -> None:
    result = verify_run_manifest(
        _manifest(),
        trust_policy=_policy(),
        backend_registry=load_backend_identity_registry(REGISTRY),
    )

    assert result.ok
    assert result.identity_status == "resolved"
    assert result.backend_registry_id == "klein-test-registry"
    assert result.registry_backend_id == "full_simulator"
    assert result.registry_key_status == "active"


def test_registry_backed_policy_without_registry_fails() -> None:
    result = verify_run_manifest(_manifest(), trust_policy=_policy())

    assert not result.ok
    assert result.error_code == "BACKEND_IDENTITY_REGISTRY_INVALID"


def test_registry_key_mismatch_fails() -> None:
    registry = _registry()
    registry["backends"][0]["keys"][0]["public_key"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

    result = verify_run_manifest(_manifest(), trust_policy=_policy(), backend_registry=registry)

    assert not result.ok
    assert result.error_code == "BACKEND_IDENTITY_KEY_MISMATCH"


def test_policy_trust_but_registry_profile_missing_fails() -> None:
    registry = _registry()
    registry["backends"][0]["profiles"][0]["profile_id"] = "other"

    result = verify_run_manifest(_manifest(), trust_policy=_policy(), backend_registry=registry)

    assert not result.ok
    assert result.error_code == "BACKEND_IDENTITY_SCOPE_MISMATCH"


def test_registry_active_key_without_policy_trust_is_untrusted() -> None:
    policy = _policy()
    policy["trusted_keys"][0]["key_id"] = "other"

    result = verify_run_manifest(_manifest(), trust_policy=policy, backend_registry=_registry())

    assert not result.ok
    assert result.error_code == "TRUST_POLICY_KEY_NOT_FOUND"


def test_registry_revoked_key_policy_trusted_is_untrusted() -> None:
    registry = _registry()
    registry["backends"][0]["keys"][0]["status"] = "revoked"

    result = verify_run_manifest(_manifest(), trust_policy=_policy(), backend_registry=registry)

    assert not result.ok
    assert result.error_code == "BACKEND_IDENTITY_KEY_REVOKED"


def test_policy_public_key_must_match_registry() -> None:
    policy = deepcopy(_policy())
    policy["trusted_keys"][0]["public_key"] = "A" * 43 + "="
    policy["trusted_keys"][0]["public_key_encoding"] = "base64.raw.ed25519"

    result = verify_run_manifest(_manifest(), trust_policy=policy, backend_registry=_registry())

    assert not result.ok
    assert result.error_code == "BACKEND_IDENTITY_KEY_MISMATCH"


def test_registry_backed_policy_schema_rejects_missing_source_without_public_key() -> None:
    policy = _policy()
    del policy["trusted_keys"][0]["source"]

    try:
        load_trust_policy(REGISTRY_POLICY)
    except TrustPolicyError:
        raise AssertionError("fixture policy should remain valid") from None
    result = verify_run_manifest(_manifest(), trust_policy=policy, backend_registry=_registry())

    assert not result.ok
    assert result.error_code == "TRUST_POLICY_SCHEMA_INVALID"

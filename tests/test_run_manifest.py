from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft7Validator

from klein.conformance.models import ConformanceVector
from klein.conformance.runner import run_manifest_details
from klein.crypto.keys import load_ed25519_private_key, load_ed25519_public_key
from klein.crypto.manifest import (
    RunManifestError,
    build_run_manifest_payload,
    load_hail_jsonl,
    load_run_manifest,
    sign_run_manifest,
    verify_run_manifest,
)
from klein.crypto.trust import evaluate_trust_policy, load_trust_policy
from klein.tools.run_manifest import main as run_manifest_main

FIXTURE_DIR = Path("tests/fixtures/run_manifest")
CRYPTO_DIR = Path("tests/fixtures/crypto")
HAIL_FIXTURE = FIXTURE_DIR / "lifecycle_stream.jsonl"
PRIVATE_KEY = CRYPTO_DIR / "backend_test_ed25519_private.pem"
PUBLIC_KEY = CRYPTO_DIR / "backend_test_ed25519_public.pem"
TRUST_POLICY = CRYPTO_DIR / "trust_policy_test.json"


def _events() -> list[dict]:
    return load_hail_jsonl(HAIL_FIXTURE)


def _manifest() -> dict:
    return load_run_manifest(FIXTURE_DIR / "run_manifest_signed.json")


def _signed_manifest(payload: dict) -> dict:
    return sign_run_manifest(
        payload,
        load_ed25519_private_key(PRIVATE_KEY),
        key_id="klein-test-backend-001",
    )


def test_run_manifest_schema_accepts_signed_fixture() -> None:
    schema = json.loads(Path("schemas/run_manifest.schema.json").read_text(encoding="utf-8"))
    Draft7Validator(schema).validate(_manifest())


def test_trust_policy_schema_accepts_test_fixture() -> None:
    schema = json.loads(Path("schemas/trust_policy.schema.json").read_text(encoding="utf-8"))
    Draft7Validator(schema).validate(load_trust_policy(TRUST_POLICY))


def test_build_payload_from_lifecycle_hail_matches_fixture() -> None:
    expected = json.loads((FIXTURE_DIR / "run_manifest_unsigned_payload.json").read_text())

    payload = build_run_manifest_payload(_events())

    assert payload == expected
    assert payload["artifact_hash"].startswith("sha256:")
    assert payload["hail_chain_digest"] == payload["preclose_hail_chain_digest"]
    assert payload["event_count"] == 7
    assert payload["event_count_preclose"] == 6


def test_signature_verifies_for_unchanged_payload() -> None:
    verification = verify_run_manifest(_manifest(), events=_events())

    assert verification.ok
    assert verification.verified_key_ids == ("klein-test-backend-001",)
    assert verification.trust_status == "not_evaluated"


def test_signature_fails_when_payload_binding_fields_change() -> None:
    for field, value in [
        ("artifact_hash", "sha256:" + "0" * 64),
        ("hail_chain_digest", "sha256:" + "1" * 64),
        ("backend_id", "other_backend"),
        ("substrate_fingerprint", "sha256:" + "2" * 64),
    ]:
        tampered = deepcopy(_manifest())
        tampered["payload"][field] = value

        verification = verify_run_manifest(tampered)

        assert not verification.ok, field
        assert verification.error_code == "RUN_MANIFEST_SIGNATURE_INVALID"


def test_signature_fails_with_wrong_public_key() -> None:
    tampered = deepcopy(_manifest())
    tampered["signatures"][0]["public_key"] = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="

    verification = verify_run_manifest(tampered)

    assert not verification.ok
    assert verification.error_code == "RUN_MANIFEST_SIGNATURE_INVALID"


def test_signature_fails_cleanly_for_malformed_base64() -> None:
    tampered = deepcopy(_manifest())
    tampered["signatures"][0]["signature"] = "not base64"

    verification = verify_run_manifest(tampered)

    assert not verification.ok
    assert verification.error_code == "RUN_MANIFEST_SIGNATURE_INVALID"


def test_hail_without_lifecycle_fails_before_signing() -> None:
    events = [
        {
            "kind": "DEVICE_EVENT",
            "t": 0,
            "timebase": "DEVICE_TICKS",
            "run_id": "R1",
            "code": "INIT",
            "level": "INFO",
            "message": "ok",
        }
    ]

    try:
        build_run_manifest_payload(events)
    except RunManifestError as exc:
        assert exc.error_code == "RUN_MANIFEST_LIFECYCLE_MISSING"
    else:  # pragma: no cover
        raise AssertionError("expected lifecycle failure")


def test_altered_run_end_chain_digest_fails_before_signing() -> None:
    events = deepcopy(_events())
    run_end = next(event for event in events if event["kind"] == "RUN_END")
    run_end["preclose_hail_chain_digest"] = "sha256:" + "0" * 64

    try:
        build_run_manifest_payload(events)
    except RunManifestError as exc:
        assert exc.error_code == "RUN_MANIFEST_CHAIN_INVALID"
    else:  # pragma: no cover
        raise AssertionError("expected chain failure")


def test_missing_artifact_hash_fails_cleanly() -> None:
    events = deepcopy(_events())
    run_start = next(event for event in events if event["kind"] == "RUN_START")
    del run_start["artifact_hash"]

    try:
        build_run_manifest_payload(events)
    except RunManifestError as exc:
        assert exc.error_code == "RUN_MANIFEST_INVALID"
    else:  # pragma: no cover
        raise AssertionError("expected manifest failure")


def test_manifest_payload_wrong_hail_digest_fails_against_hail() -> None:
    payload = build_run_manifest_payload(_events())
    payload["hail_digest"] = "sha256:" + "9" * 64
    manifest = _signed_manifest(payload)

    verification = verify_run_manifest(manifest, events=_events())

    assert not verification.ok
    assert verification.error_code in {
        "RUN_MANIFEST_CHAIN_INVALID",
        "RUN_MANIFEST_PAYLOAD_MISMATCH",
    }


def test_manifest_fails_against_tampered_hail_event_and_chain() -> None:
    events = deepcopy(_events())
    device_event = next(event for event in events if event.get("kind") == "DEVICE_EVENT")
    device_event["message"] = "tampered"

    verification = verify_run_manifest(_manifest(), events=events)

    assert not verification.ok
    assert verification.error_code in {
        "RUN_MANIFEST_CHAIN_INVALID",
        "RUN_MANIFEST_PAYLOAD_MISMATCH",
    }


def test_manifest_fails_when_hail_run_start_backend_differs() -> None:
    events = deepcopy(_events())
    run_start = next(event for event in events if event["kind"] == "RUN_START")
    run_start["backend_id"] = "other_backend"

    verification = verify_run_manifest(_manifest(), events=events)

    assert not verification.ok
    assert verification.error_code in {
        "RUN_MANIFEST_CHAIN_INVALID",
        "RUN_MANIFEST_PAYLOAD_MISMATCH",
    }


def test_trust_policy_statuses() -> None:
    manifest = _manifest()
    policy = load_trust_policy(TRUST_POLICY)

    no_policy = verify_run_manifest(manifest)
    trusted = verify_run_manifest(
        manifest,
        trusted_key_id="klein-test-backend-001",
        trusted_public_key=load_ed25519_public_key(PUBLIC_KEY),
    )
    untrusted = verify_run_manifest(manifest, trusted_key_id="some-other-key")

    assert no_policy.ok
    assert no_policy.trust_status == "not_evaluated"
    assert trusted.ok
    assert trusted.trust_status == "trusted"
    assert not untrusted.ok
    assert untrusted.trust_status == "untrusted"
    assert untrusted.error_code == "BACKEND_IDENTITY_UNTRUSTED"

    policy_trusted = verify_run_manifest(manifest, trust_policy=policy)
    assert policy_trusted.ok
    assert policy_trusted.trust_status == "trusted"
    assert policy_trusted.trust_reason == "policy_scope_match"


def test_trust_policy_rejects_wrong_backend_profile_revoked_and_unknown_key() -> None:
    manifest = _manifest()
    signature = manifest["signatures"][0]
    policy = load_trust_policy(TRUST_POLICY)

    wrong_backend = deepcopy(manifest)
    wrong_backend["payload"]["backend_id"] = "other_backend"
    backend_result = evaluate_trust_policy(policy, manifest=wrong_backend, signature=signature)

    wrong_profile = deepcopy(manifest)
    wrong_profile["payload"]["profile_id"] = "other_profile"
    profile_result = evaluate_trust_policy(policy, manifest=wrong_profile, signature=signature)

    revoked_policy = deepcopy(policy)
    revoked_policy["revoked_keys"] = [deepcopy(policy["trusted_keys"][0])]
    revoked_result = evaluate_trust_policy(revoked_policy, manifest=manifest, signature=signature)

    unknown_signature = deepcopy(signature)
    unknown_signature["key_id"] = "unknown-key"
    unknown_result = evaluate_trust_policy(policy, manifest=manifest, signature=unknown_signature)

    assert not backend_result.trusted
    assert backend_result.error_code == "TRUST_POLICY_SCOPE_MISMATCH"
    assert backend_result.trust_reason == "backend_id_not_allowed"
    assert not profile_result.trusted
    assert profile_result.error_code == "TRUST_POLICY_SCOPE_MISMATCH"
    assert profile_result.trust_reason == "profile_id_not_allowed"
    assert not revoked_result.trusted
    assert revoked_result.error_code == "TRUST_POLICY_KEY_REVOKED"
    assert not unknown_result.trusted
    assert unknown_result.error_code == "TRUST_POLICY_KEY_NOT_FOUND"


def test_valid_signature_with_untrusted_policy_is_not_invalid_signature() -> None:
    manifest = _manifest()
    policy = load_trust_policy(TRUST_POLICY)
    policy["trusted_keys"][0]["trust_scope"]["backend_ids"] = ["not_full_simulator"]

    verification = verify_run_manifest(manifest, trust_policy=policy)

    assert not verification.ok
    assert verification.signature_status == "valid"
    assert verification.trust_status == "untrusted"
    assert verification.error_code == "TRUST_POLICY_SCOPE_MISMATCH"


def test_run_manifest_cli_create_verify_inspect(tmp_path: Path, capsys) -> None:
    output = tmp_path / "run_manifest.json"

    assert run_manifest_main([
        "create",
        "--hail",
        str(HAIL_FIXTURE),
        "--private-key",
        str(PRIVATE_KEY),
        "--key-id",
        "klein-test-backend-001",
        "--output",
        str(output),
    ]) == 0
    assert run_manifest_main(["verify", "--manifest", str(output), "--hail", str(HAIL_FIXTURE)]) == 0
    assert run_manifest_main([
        "verify",
        "--manifest",
        str(output),
        "--hail",
        str(HAIL_FIXTURE),
        "--trust-policy",
        str(TRUST_POLICY),
    ]) == 0
    assert run_manifest_main(["inspect", "--manifest", str(output)]) == 0

    captured = capsys.readouterr()
    assert "Run Manifest verified" in captured.out
    assert "trust_status=trusted" in captured.out
    assert "R011" in captured.out


def test_conformance_manifest_details_verify_against_events() -> None:
    vector = ConformanceVector(
        id="manifest-fixture",
        name="manifest fixture",
        purpose="exercise optional signed manifest report fields",
        schema_version="v1",
        run_manifest_path=FIXTURE_DIR / "run_manifest_signed.json",
        trust_policy_path=FIXTURE_DIR / "trust_policy_test.json",
        signed_conformance=True,
    )

    details = run_manifest_details(vector, _events())

    assert details["run_manifest_present"] is True
    assert details["run_manifest_verified"] is True
    assert details["run_manifest_signature_status"] == "valid"
    assert details["run_manifest_trust_status"] == "trusted"
    assert details["run_manifest_key_id"] == "klein-test-backend-001"
    assert details["run_manifest_signature_algorithm"] == "Ed25519"
    assert details["run_manifest_error_code"] is None

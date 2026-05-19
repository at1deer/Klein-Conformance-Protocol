from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft7Validator

from klein.crypto.manifest import load_run_manifest, verify_run_manifest
from klein.crypto.trust import evaluate_trust_policy, load_trust_policy
from klein.tools.verify_run import main as verify_run_main
from klein.verifier import verify_signed_conformance

FIXTURE_DIR = Path("tests/fixtures/signed_conformance")
HAIL = FIXTURE_DIR / "hail.jsonl"
MANIFEST = FIXTURE_DIR / "manifest_signed.json"
TRUST_POLICY = FIXTURE_DIR / "trust_policy.json"


def _write_json(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_signed_conformance_result_matches_schema_and_fixture() -> None:
    schema = json.loads(Path("schemas/signed_conformance_result.schema.json").read_text())
    expected = json.loads((FIXTURE_DIR / "expected_result.json").read_text())

    result = verify_signed_conformance(
        hail_path=HAIL,
        manifest_path=MANIFEST,
        trust_policy_path=TRUST_POLICY,
    ).to_dict()

    Draft7Validator(schema).validate(result)
    assert result == expected


def test_klein_verify_run_cli_human_and_json(capsys) -> None:
    assert verify_run_main([
        "--hail",
        str(HAIL),
        "--manifest",
        str(MANIFEST),
        "--trust-policy",
        str(TRUST_POLICY),
    ]) == 0
    assert verify_run_main([
        "--hail",
        str(HAIL),
        "--manifest",
        str(MANIFEST),
        "--trust-policy",
        str(TRUST_POLICY),
        "--json",
    ]) == 0

    captured = capsys.readouterr()
    assert "KCP-Core-Signed-Conformance-v1: pass" in captured.out
    json_text = captured.out[captured.out.index("{") :]
    assert json.loads(json_text)["overall_status"] == "pass"


def test_signed_conformance_requires_trusted_policy() -> None:
    result = verify_signed_conformance(
        hail_path=HAIL,
        manifest_path=MANIFEST,
        trust_policy_path=None,
    )

    assert not result.ok
    assert result.trust_status == "not_evaluated"
    assert result.errors[0]["error_code"] == "BACKEND_IDENTITY_UNTRUSTED"


def test_signed_conformance_detects_tampered_payload(tmp_path: Path) -> None:
    manifest = load_run_manifest(MANIFEST)
    manifest["payload"]["created_by"] = "tampered-after-signing"
    manifest_path = _write_json(tmp_path / "manifest.json", manifest)

    result = verify_signed_conformance(
        hail_path=HAIL,
        manifest_path=manifest_path,
        trust_policy_path=TRUST_POLICY,
    )

    assert not result.ok
    assert result.signature_status == "fail"
    assert result.errors[0]["error_code"] == "RUN_MANIFEST_SIGNATURE_INVALID"


def test_signed_conformance_detects_trust_scope_mismatch(tmp_path: Path) -> None:
    policy = load_trust_policy(TRUST_POLICY)
    policy["trusted_keys"][0]["trust_scope"]["profile_ids"] = ["other_profile"]
    policy_path = _write_json(tmp_path / "trust_policy.json", policy)

    result = verify_signed_conformance(
        hail_path=HAIL,
        manifest_path=MANIFEST,
        trust_policy_path=policy_path,
    )

    assert not result.ok
    assert result.signature_status == "pass"
    assert result.trust_status == "fail"
    assert result.errors[0]["error_code"] == "TRUST_POLICY_SCOPE_MISMATCH"


def test_trust_policy_time_and_schema_edges(tmp_path: Path) -> None:
    manifest = load_run_manifest(MANIFEST)
    policy = load_trust_policy(TRUST_POLICY)

    expired = deepcopy(policy)
    expired["trusted_keys"][0]["not_after"] = "2000-01-01T00:00:00Z"
    expired_manifest = deepcopy(manifest)
    expired_manifest["payload"]["created_at"] = "2001-01-01T00:00:00Z"
    expired_result = evaluate_trust_policy(
        expired,
        manifest=expired_manifest,
        signature=expired_manifest["signatures"][0],
    )

    created_at_missing = deepcopy(policy)
    created_at_missing["trusted_keys"][0]["not_before"] = "2000-01-01T00:00:00Z"
    indeterminate_result = verify_run_manifest(manifest, trust_policy=created_at_missing)

    malformed_path = _write_json(tmp_path / "bad_policy.json", {"policy_version": "bad"})
    malformed_result = verify_signed_conformance(
        hail_path=HAIL,
        manifest_path=MANIFEST,
        trust_policy_path=malformed_path,
    )

    assert expired_result.trust_status == "untrusted"
    assert expired_result.trust_reason == "manifest_after_key_validity"
    assert not indeterminate_result.ok
    assert indeterminate_result.trust_status == "indeterminate"
    assert indeterminate_result.trust_reason == "manifest_created_at_missing"
    assert not malformed_result.ok
    assert malformed_result.errors[0]["error_code"] == "TRUST_POLICY_SCHEMA_INVALID"

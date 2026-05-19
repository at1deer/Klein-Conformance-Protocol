from __future__ import annotations

import inspect
import json
import zipfile
from copy import deepcopy
from pathlib import Path

from jsonschema import Draft7Validator

from klein.bundle import create_run_bundle
from klein.crypto.manifest import load_run_manifest
from klein.tools.verify_bundle import main as verify_bundle_main
from klein.verifier.independent import verify_bundle_independently

VECTOR_012 = Path("tests/vectors/v1/core/012_hard_signed_run_manifest")

def _bundle(tmp_path: Path) -> Path:
    output = tmp_path / "valid.kcprun"
    create_run_bundle(
        artifact_path=VECTOR_012 / "input/container.kleinc",
        hail_path=VECTOR_012 / "golden/observables.jsonl",
        manifest_path=VECTOR_012 / "manifest/run_manifest_signed.json",
        trust_policy_path=VECTOR_012 / "manifest/trust_policy.json",
        output_path=output,
    )
    return output


def _copy_zip_with_changes(source: Path, target: Path, replace: dict[str, bytes]) -> Path:
    with zipfile.ZipFile(source, "r") as src, zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as dst:
        for info in src.infolist():
            data = replace.get(info.filename, src.read(info.filename))
            dst.writestr(info.filename, data)
    return target


def test_independent_verifier_positive_json_matches_schema(tmp_path: Path) -> None:
    schema = json.loads(Path("schemas/independent_verifier_result.schema.json").read_text())

    result = verify_bundle_independently(_bundle(tmp_path))

    assert result.ok
    assert result.checks["bundle_schema"] == "pass"
    assert result.checks["run_manifest_signature"] == "pass"
    assert result.bindings["trusted_key_ids"] == ["klein-test-backend-001"]
    Draft7Validator(schema).validate(result.to_dict())


def test_klein_verify_bundle_cli_human_and_json(tmp_path: Path, capsys) -> None:
    bundle = _bundle(tmp_path)

    assert verify_bundle_main([str(bundle)]) == 0
    assert verify_bundle_main([str(bundle), "--json"]) == 0

    captured = capsys.readouterr()
    assert "Independent verifier: overall_status=pass" in captured.out
    assert '"result_version": "klein.independent_verifier_result.v1"' in captured.out


def test_independent_verifier_negative_bundles(tmp_path: Path) -> None:
    source = _bundle(tmp_path)
    manifest = load_run_manifest(VECTOR_012 / "manifest/run_manifest_signed.json")
    policy = json.loads((VECTOR_012 / "manifest/trust_policy.json").read_text(encoding="utf-8"))

    chain_mismatch_hail = (VECTOR_012 / "golden/observables.jsonl").read_text(encoding="utf-8").replace(
        "FRAME_APPLIED",
        "FRAME_TAMPERED",
        1,
    )

    signature_invalid = deepcopy(manifest)
    signature_invalid["payload"]["created_by"] = "tampered-after-signing"

    untrusted_policy = deepcopy(policy)
    untrusted_policy["trusted_keys"][0]["trust_scope"]["backend_ids"] = ["other_backend"]

    cases = {
        "bundle_hash_mismatch.kcprun": (
            {"trust/trust_policy.json": json.dumps(untrusted_policy, sort_keys=True).encode()},
            "RUN_BUNDLE_HASH_MISMATCH",
        ),
        "hail_chain_mismatch.kcprun": (
            {
                "hail/observables.jsonl": chain_mismatch_hail.encode(),
                "bundle.json": _bundle_json_with_hash(source, "hail", chain_mismatch_hail.encode()),
            },
            "HAIL_CHAIN_MISMATCH",
        ),
        "manifest_signature_invalid.kcprun": (
            {
                "manifest/run_manifest.json": json.dumps(signature_invalid, sort_keys=True).encode(),
                "bundle.json": _bundle_json_with_hash(
                    source,
                    "run_manifest",
                    json.dumps(signature_invalid, sort_keys=True).encode(),
                ),
            },
            "RUN_MANIFEST_SIGNATURE_INVALID",
        ),
        "trust_policy_untrusted.kcprun": (
            {
                "trust/trust_policy.json": json.dumps(untrusted_policy, sort_keys=True).encode(),
                "bundle.json": _bundle_json_with_hashes(
                    source,
                    {
                        "trust_policy": json.dumps(untrusted_policy, sort_keys=True).encode(),
                    },
                ),
            },
            "TRUST_POLICY_SCOPE_MISMATCH",
        ),
    }

    for name, (replace, expected_code) in cases.items():
        bundle = _copy_zip_with_changes(source, tmp_path / name, replace)
        result = verify_bundle_independently(bundle)

        assert not result.ok, name
        assert result.errors[0]["error_code"] == expected_code


def test_independent_verifier_import_boundary() -> None:
    import klein.verifier.independent as independent

    source = inspect.getsource(independent)

    assert "klein.sim" not in source
    assert "klein.conformance" not in source
    assert "tests/vectors" not in source


def test_cross_language_fixture_index_names_independent_bundle_fixture() -> None:
    index = json.loads(Path("tests/fixtures/cross_language/fixtures.json").read_text())
    fixture_ids = {fixture["fixture_id"] for fixture in index["fixtures"]}

    assert "valid-kcprun-bundle-v1" in fixture_ids
    assert "kcprun-path-traversal-negative-v1" in fixture_ids
    for fixture in index["fixtures"]:
        assert "python" in fixture["target_implementations"]


def _bundle_json_with_hash(source: Path, key: str, payload: bytes) -> bytes:
    return _bundle_json_with_hashes(source, {key: payload})


def _bundle_json_with_hashes(source: Path, payloads: dict[str, bytes]) -> bytes:
    import hashlib

    with zipfile.ZipFile(source, "r") as archive:
        bundle = json.loads(archive.read("bundle.json"))
    for key, payload in payloads.items():
        bundle["hashes"][key] = f"sha256:{hashlib.sha256(payload).hexdigest()}"
    return json.dumps(bundle, indent=2, sort_keys=True).encode()

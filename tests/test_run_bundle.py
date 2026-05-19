from __future__ import annotations

import json
import warnings
import zipfile
from pathlib import Path

from jsonschema import Draft7Validator

from klein.bundle import create_run_bundle, inspect_run_bundle, verify_run_bundle
from klein.tools.run_bundle import main as run_bundle_main

FIXTURE_DIR = Path("tests/fixtures/run_bundle")
VECTOR_012 = Path("tests/vectors/v1/core/012_hard_signed_run_manifest")


def test_run_bundle_schema_accepts_fixture() -> None:
    schema = json.loads(Path("schemas/run_bundle.schema.json").read_text(encoding="utf-8"))
    bundle = json.loads((FIXTURE_DIR / "valid_signed_run_dir/bundle.json").read_text(encoding="utf-8"))

    Draft7Validator(schema).validate(bundle)


def test_run_bundle_verify_zip_and_directory_match_result_schema() -> None:
    schema = json.loads(Path("schemas/run_bundle_result.schema.json").read_text(encoding="utf-8"))

    zip_result = verify_run_bundle(FIXTURE_DIR / "valid_signed_run.kcprun")
    dir_result = verify_run_bundle(FIXTURE_DIR / "valid_signed_run_dir")

    assert zip_result.ok
    assert dir_result.ok
    assert zip_result.bundle_format == "zip"
    assert dir_result.bundle_format == "directory"
    assert zip_result.signed_conformance_status == "pass"
    assert zip_result.artifact_schema_status == "pass"
    assert zip_result.artifact_type == "container"
    assert zip_result.artifact_canonicalization == "klein.canon.json.v1"
    assert zip_result.run_manifest_key_ids == ["klein-test-backend-001"]
    Draft7Validator(schema).validate(zip_result.to_dict())


def test_run_bundle_with_backend_registry_verifies() -> None:
    result = verify_run_bundle(FIXTURE_DIR / "valid_signed_run_with_registry.kcprun")

    assert result.ok
    assert result.backend_registry_hash is not None
    assert result.signed_conformance_result is not None
    assert result.signed_conformance_result["identity_status"] == "resolved"


def test_run_bundle_cli_create_verify_inspect(tmp_path: Path, capsys) -> None:
    bundle = tmp_path / "run.kcprun"

    assert run_bundle_main([
        "create",
        "--artifact",
        str(VECTOR_012 / "input/container.kleinc"),
        "--hail",
        str(VECTOR_012 / "golden/observables.jsonl"),
        "--manifest",
        str(VECTOR_012 / "manifest/run_manifest_signed.json"),
        "--trust-policy",
        str(VECTOR_012 / "manifest/trust_policy.json"),
        "--output",
        str(bundle),
    ]) == 0
    assert run_bundle_main(["verify", "--bundle", str(bundle)]) == 0
    assert run_bundle_main(["verify", "--bundle", str(bundle), "--json"]) == 0
    assert run_bundle_main(["inspect", "--bundle", str(bundle)]) == 0

    captured = capsys.readouterr()
    assert "Run Bundle created" in captured.out
    assert "overall_status=pass" in captured.out
    assert '"overall_status": "pass"' in captured.out
    assert "artifact/input.kleinc" in captured.out


def test_run_bundle_negative_fixtures_report_canonical_errors() -> None:
    expected = {
        "tampered_hail.kcprun": "RUN_BUNDLE_HASH_MISMATCH",
        "hash_mismatch.kcprun": "RUN_BUNDLE_HASH_MISMATCH",
        "missing_manifest.kcprun": "RUN_BUNDLE_MISSING_ENTRY",
        "path_traversal_attack.kcprun": "RUN_BUNDLE_PATH_TRAVERSAL",
    }

    for fixture_name, error_code in expected.items():
        result = verify_run_bundle(FIXTURE_DIR / fixture_name)

        assert not result.ok, fixture_name
        assert result.errors[0]["error_code"] == error_code


def test_run_bundle_rejects_duplicate_bundle_json(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.kcprun"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(duplicate, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("bundle.json", "{}")
            archive.writestr("bundle.json", "{}")

    result = verify_run_bundle(duplicate)

    assert not result.ok
    assert result.errors[0]["error_code"] == "RUN_BUNDLE_INVALID"


def test_create_directory_bundle_and_inspect(tmp_path: Path) -> None:
    output = tmp_path / "run.kcpbundle"

    create_run_bundle(
        artifact_path=VECTOR_012 / "input/container.kleinc",
        hail_path=VECTOR_012 / "golden/observables.jsonl",
        manifest_path=VECTOR_012 / "manifest/run_manifest_signed.json",
        trust_policy_path=VECTOR_012 / "manifest/trust_policy.json",
        output_path=output,
        directory=True,
        include_signed_conformance_report=True,
    )
    info = inspect_run_bundle(output)
    result = verify_run_bundle(output)

    assert info["bundle_format"] == "directory"
    assert (output / "conformance/signed_conformance.json").exists()
    assert result.ok

"""Create KCP Run Bundle v1 directory and archive artifacts."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from klein.bundle.archive import copy_entry, write_zip_bundle
from klein.bundle.model import RUN_BUNDLE_VERSION, RunBundleError
from klein.common.hashing import raw_file_sha256
from klein.verifier.signed_conformance import verify_signed_conformance


def create_run_bundle(
    *,
    artifact_path: Path,
    hail_path: Path,
    manifest_path: Path,
    trust_policy_path: Path,
    output_path: Path,
    directory: bool = False,
    conformance_report_path: Path | None = None,
    backend_registry_path: Path | None = None,
    backend_capabilities_path: Path | None = None,
    include_signed_conformance_report: bool = False,
    bundle_id: str | None = None,
    created_by: str = "klein-protocol",
    created_at: str | None = None,
) -> Path:
    """Create a KCP Run Bundle v1 in directory form or canonical .kcprun zip form."""
    for required in (artifact_path, hail_path, manifest_path, trust_policy_path):
        if not required.exists():
            raise RunBundleError("RUN_BUNDLE_MISSING_ENTRY", f"required input missing: {required}")

    if directory:
        _create_bundle_dir(
            root=output_path,
            artifact_path=artifact_path,
            hail_path=hail_path,
            manifest_path=manifest_path,
            trust_policy_path=trust_policy_path,
            conformance_report_path=conformance_report_path,
            backend_registry_path=backend_registry_path,
            backend_capabilities_path=backend_capabilities_path,
            include_signed_conformance_report=include_signed_conformance_report,
            bundle_id=bundle_id,
            created_by=created_by,
            created_at=created_at,
        )
        return output_path

    if output_path.suffix != ".kcprun":
        raise RunBundleError("RUN_BUNDLE_UNSUPPORTED_FORMAT", "zip bundle output must use .kcprun")

    with tempfile.TemporaryDirectory(prefix="klein-create-bundle-") as temp_dir:
        temp_root = Path(temp_dir) / "run.kcpbundle"
        _create_bundle_dir(
            root=temp_root,
            artifact_path=artifact_path,
            hail_path=hail_path,
            manifest_path=manifest_path,
            trust_policy_path=trust_policy_path,
            conformance_report_path=conformance_report_path,
            backend_registry_path=backend_registry_path,
            backend_capabilities_path=backend_capabilities_path,
            include_signed_conformance_report=include_signed_conformance_report,
            bundle_id=bundle_id,
            created_by=created_by,
            created_at=created_at,
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        write_zip_bundle(temp_root, output_path)
    return output_path


def _create_bundle_dir(
    *,
    root: Path,
    artifact_path: Path,
    hail_path: Path,
    manifest_path: Path,
    trust_policy_path: Path,
    conformance_report_path: Path | None,
    backend_registry_path: Path | None,
    backend_capabilities_path: Path | None,
    include_signed_conformance_report: bool,
    bundle_id: str | None,
    created_by: str,
    created_at: str | None,
) -> None:
    if root.exists() and any(root.iterdir()):
        raise RunBundleError("RUN_BUNDLE_INVALID", f"output directory already exists and is not empty: {root}")
    entries: dict[str, str | None] = {
        "artifact": f"artifact/{_artifact_name(artifact_path)}",
        "hail": "hail/observables.jsonl",
        "run_manifest": "manifest/run_manifest.json",
        "trust_policy": "trust/trust_policy.json",
        "conformance_report": "conformance/report.json" if conformance_report_path is not None else None,
        "signed_conformance_report": (
            "conformance/signed_conformance.json" if include_signed_conformance_report else None
        ),
        "backend_registry": "identity/backend_registry.json" if backend_registry_path is not None else None,
        "backend_capabilities": "identity/backend_capabilities.json" if backend_capabilities_path is not None else None,
    }
    copies: dict[str, Path] = {
        "artifact": artifact_path,
        "hail": hail_path,
        "run_manifest": manifest_path,
        "trust_policy": trust_policy_path,
    }
    if conformance_report_path is not None:
        copies["conformance_report"] = conformance_report_path
    if backend_registry_path is not None:
        copies["backend_registry"] = backend_registry_path
    if backend_capabilities_path is not None:
        copies["backend_capabilities"] = backend_capabilities_path

    root.mkdir(parents=True, exist_ok=True)
    for key, source in copies.items():
        target = root / str(entries[key])
        copy_entry(source, target)

    if include_signed_conformance_report:
        result = verify_signed_conformance(
            hail_path=root / str(entries["hail"]),
            manifest_path=root / str(entries["run_manifest"]),
            trust_policy_path=root / str(entries["trust_policy"]),
            artifact_path=root / str(entries["artifact"]),
            conformance_report_path=(
                root / str(entries["conformance_report"])
                if entries["conformance_report"] is not None
                else None
            ),
            backend_registry_path=(
                root / str(entries["backend_registry"])
                if entries["backend_registry"] is not None
                else None
            ),
        )
        signed_report = root / str(entries["signed_conformance_report"])
        signed_report.parent.mkdir(parents=True, exist_ok=True)
        signed_report.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    bundle = {
        "bundle_version": RUN_BUNDLE_VERSION,
        "bundle_id": bundle_id,
        "created_by": created_by,
        "created_at": created_at,
        "entries": entries,
        "hashes": _entry_hashes(root, entries),
    }
    (root / "bundle.json").write_text(json.dumps(bundle, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _entry_hashes(root: Path, entries: dict[str, str | None]) -> dict[str, str | None]:
    hashes: dict[str, str | None] = {}
    for key, entry in entries.items():
        hashes[key] = raw_file_sha256(root / entry).ref if entry is not None else None
    return hashes


def _artifact_name(path: Path) -> str:
    suffix = path.suffix
    return "input.kleinc" if suffix == ".kleinc" else "input.klein"

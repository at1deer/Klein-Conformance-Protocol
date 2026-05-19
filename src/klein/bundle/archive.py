"""Safe KCP Run Bundle v1 archive handling."""

from __future__ import annotations

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

from klein.bundle.model import (
    RUN_BUNDLE_EXTENSION,
    RunBundle,
    RunBundleError,
    declared_entry_paths,
    validate_run_bundle_structure,
)
from klein.common.hashing import parse_ijson


@dataclass
class BundleSource:
    """Prepared bundle files available as local paths."""

    root: Path
    bundle: RunBundle
    bundle_format: str
    cleanup: tempfile.TemporaryDirectory[str] | None = None

    def close(self) -> None:
        if self.cleanup is not None:
            self.cleanup.cleanup()


def bundle_format(path: Path) -> str:
    if path.is_dir():
        return "directory"
    if path.is_file() and path.suffix == RUN_BUNDLE_EXTENSION:
        return "zip"
    raise RunBundleError("RUN_BUNDLE_UNSUPPORTED_FORMAT", "bundle must be a directory or .kcprun file")


def load_bundle_source(path: Path) -> BundleSource:
    """Load a directory or .kcprun bundle without unsafe archive extraction."""
    fmt = bundle_format(path)
    if fmt == "directory":
        bundle = _load_directory_manifest(path)
        _validate_directory_members(path, bundle)
        return BundleSource(root=path, bundle=bundle, bundle_format=fmt)
    return _load_zip_bundle(path)


def write_zip_bundle(source_dir: Path, output_path: Path) -> None:
    """Write a canonical .kcprun zip from a prepared bundle directory."""
    files = sorted(p for p in source_dir.rglob("*") if p.is_file())
    with ZipFile(output_path, "w", compression=ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, _portable_relative(file_path.relative_to(source_dir)))


def _load_directory_manifest(root: Path) -> RunBundle:
    bundle_path = root / "bundle.json"
    if not bundle_path.exists():
        raise RunBundleError("RUN_BUNDLE_MISSING_ENTRY", "bundle.json is required")
    try:
        data = parse_ijson(bundle_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RunBundleError("RUN_BUNDLE_INVALID", f"bundle.json parse failed: {exc}") from exc
    return validate_run_bundle_structure(data)


def _validate_directory_members(root: Path, bundle: RunBundle) -> None:
    expected = {"bundle.json"} | declared_entry_paths(bundle)
    actual = {
        _portable_relative(path.relative_to(root))
        for path in root.rglob("*")
        if path.is_file()
    }
    extra = actual - expected
    if extra:
        raise RunBundleError(
            "RUN_BUNDLE_INVALID",
            f"bundle contains undeclared file(s): {', '.join(sorted(extra))}",
        )


def _load_zip_bundle(path: Path) -> BundleSource:
    with ZipFile(path) as archive:
        names = [info.filename for info in archive.infolist() if not info.is_dir()]
        _validate_zip_member_names(names)
        if "bundle.json" not in names:
            raise RunBundleError("RUN_BUNDLE_MISSING_ENTRY", "bundle.json is required")
        try:
            bundle_data = parse_ijson(archive.read("bundle.json").decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise RunBundleError("RUN_BUNDLE_INVALID", f"bundle.json parse failed: {exc}") from exc
        bundle = validate_run_bundle_structure(bundle_data)
        expected = {"bundle.json"} | declared_entry_paths(bundle)
        actual = set(names)
        extra = actual - expected
        if extra:
            raise RunBundleError(
                "RUN_BUNDLE_INVALID",
                f"bundle contains undeclared file(s): {', '.join(sorted(extra))}",
            )
        missing = expected - actual
        if missing:
            raise RunBundleError(
                "RUN_BUNDLE_MISSING_ENTRY",
                f"bundle is missing declared file(s): {', '.join(sorted(missing))}",
            )

        temp = tempfile.TemporaryDirectory(prefix="klein-bundle-")
        root = Path(temp.name)
        for name in sorted(expected):
            target = root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(archive.read(name))
        return BundleSource(root=root, bundle=bundle, bundle_format="zip", cleanup=temp)


def _validate_zip_member_names(names: list[str]) -> None:
    if len(names) != len(set(names)):
        raise RunBundleError("RUN_BUNDLE_INVALID", "zip bundle contains duplicate member names")
    for name in names:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name:
            raise RunBundleError(
                "RUN_BUNDLE_PATH_TRAVERSAL",
                f"zip bundle contains unsafe member path: {name}",
            )


def _portable_relative(path: Path) -> str:
    return path.as_posix()


def copy_entry(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)

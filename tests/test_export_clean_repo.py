from __future__ import annotations

import zipfile
from pathlib import Path

from klein.tools.export_clean_repo import build_archive, clean_file_list, repo_root

IGNORED_PARTS = {
    ".git",
    ".venv",
    ".pytest_cache",
    ".ruff_cache",
    "target",
    "__pycache__",
}


def test_clean_export_file_list_excludes_local_artifacts(tmp_path: Path) -> None:
    root = repo_root(Path.cwd())
    files = clean_file_list(root, tmp_path / "klein-clean.zip")
    names = [path.as_posix() for path in files]

    assert names
    for name in names:
        assert not any(part in name.split("/") for part in IGNORED_PARTS)
        assert not name.endswith(".pyc")
        assert not name.startswith("verifiers/rust/target/")


def test_clean_export_archive_excludes_local_artifacts(tmp_path: Path) -> None:
    root = repo_root(Path.cwd())
    output = tmp_path / "klein-clean.zip"
    files = clean_file_list(root, output)

    build_archive(root, output, files)

    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()

    assert "README.md" in names
    for name in names:
        assert not any(part in name.split("/") for part in IGNORED_PARTS)
        assert not name.endswith(".pyc")
        assert not name.startswith("verifiers/rust/target/")

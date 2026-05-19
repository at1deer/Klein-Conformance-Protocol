"""Create a clean Klein repo archive without ignored local artifacts."""

from __future__ import annotations

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path


def git_lines(repo: Path, *args: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def repo_root(start: Path) -> Path:
    result = subprocess.run(
        ["git", "-C", str(start), "rev-parse", "--show-toplevel"],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def clean_file_list(repo: Path, output: Path) -> list[Path]:
    files = git_lines(repo, "ls-files", "--cached", "--others", "--exclude-standard")
    output_abs = output.resolve()
    clean: list[Path] = []
    for item in files:
        path = (repo / item).resolve()
        if path == output_abs:
            continue
        if path.is_file():
            clean.append(Path(item))
    return clean


def build_archive(repo: Path, output: Path, files: list[Path]) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relpath in files:
            archive.write(repo / relpath, relpath.as_posix())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        "-o",
        default="klein-conformance-clean.zip",
        help="Archive path to create. Default: klein-conformance-clean.zip",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would be archived without writing the zip file.",
    )
    args = parser.parse_args(argv)

    try:
        root = repo_root(Path.cwd())
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        files = clean_file_list(root, output)
        if args.dry_run:
            print(f"Would archive {len(files)} files to {output}")
            print("File list comes from: git ls-files --cached --others --exclude-standard")
            print("Ignored/local artifacts such as .venv, .pytest_cache, .ruff_cache, and target/ are excluded.")
            return 0
        build_archive(root, output, files)
        print(f"Archived {len(files)} files to {output}")
        return 0
    except subprocess.CalledProcessError as exc:
        print(exc.stderr or str(exc), file=sys.stderr)
        return exc.returncode or 1


if __name__ == "__main__":
    raise SystemExit(main())

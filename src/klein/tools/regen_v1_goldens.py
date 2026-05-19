#!/usr/bin/env python3
"""Regenerate or check authoritative v1 golden HAIL streams."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from klein.conformance.harness import (
    VECTOR_INPUT_MISSING,
    BackendType,
    create_backend,
    discover_vectors,
)
from klein.hail.canonical import canonicalize_events, normalize_run_metadata
from klein.hail.validation import validate_events


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="klein-regen-v1-goldens",
        description="Regenerate or check positive Klein Core v1 golden HAIL JSONL files.",
    )
    parser.add_argument("--suite", type=Path, default=Path("tests/vectors/v1"))
    parser.add_argument(
        "--backend",
        choices=["full_simulator"],
        default="full_simulator",
        help="Execution backend. v1 golden generation currently requires full_simulator.",
    )
    parser.add_argument("--check", action="store_true", help="Check without overwriting goldens.")
    return parser.parse_args(argv)


def _golden_lines(events: list[dict], *, normalize: bool) -> list[str]:
    payload = normalize_run_metadata(events) if normalize else events
    return canonicalize_events(payload)


def _read_existing(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    vectors = discover_vectors(category="positive", suite_dir=args.suite)
    backend = create_backend(BackendType(args.backend))
    changed: list[str] = []
    failed: list[str] = []

    try:
        for vector in vectors:
            if not vector.input_type or vector.input_path is None or not vector.input_path.exists():
                failed.append(f"{vector.id}: {VECTOR_INPUT_MISSING}")
                continue

            result = backend.execute(vector)
            if not result.success:
                failed.append(f"{vector.id}: execution failed {result.error_code or result.error_message}")
                continue
            validation = validate_events(result.events)
            if not validation.ok:
                failed.append(f"{vector.id}: generated HAIL invalid {validation.error_code}")
                continue

            generated = _golden_lines(result.events, normalize=vector.normalize_run_metadata)
            golden_path = vector.folder / "golden" / "observables.jsonl" if vector.folder else None
            if golden_path is None:
                failed.append(f"{vector.id}: vector folder is not set")
                continue
            existing = _read_existing(golden_path)
            if existing != generated:
                changed.append(vector.id)
                if not args.check:
                    golden_path.parent.mkdir(parents=True, exist_ok=True)
                    golden_path.write_text("\n".join(generated) + "\n", encoding="utf-8")
    finally:
        backend.cleanup()

    for vector_id in changed:
        action = "would change" if args.check else "regenerated"
        print(f"{action}: {vector_id}")
    for failure in failed:
        print(f"failed: {failure}", file=sys.stderr)

    if failed or (args.check and changed):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

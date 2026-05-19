"""CLI for validating, inspecting, and hashing Klein artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.artifacts import (
    ArtifactValidationError,
    canonical_artifact_hash,
    validate_artifact,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein-artifact", description="Inspect, validate, and hash Klein artifacts.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("inspect", "validate", "hash"):
        command = subparsers.add_parser(name)
        command.add_argument("path", type=Path)
    return parser


def _validate(args: argparse.Namespace) -> int:
    result = validate_artifact(args.path)
    output = result.__dict__
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(
            "Artifact valid: "
            f"type={result.artifact_type} form={result.artifact_form} "
            f"profile={result.profile_id}/{result.profile_version} mode={result.mode}"
        )
    return 0 if result.ok else 1


def _inspect(args: argparse.Namespace) -> int:
    result = validate_artifact(args.path)
    digest = canonical_artifact_hash(args.path)
    output = {**result.__dict__, "artifact_hash": digest.ref, "canonicalization": digest.canonicalization}
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(
            "Artifact: "
            f"type={result.artifact_type} form={result.artifact_form} "
            f"hash={digest.ref} canonicalization={digest.canonicalization}"
        )
    return 0 if result.ok else 1


def _hash(args: argparse.Namespace) -> int:
    digest = canonical_artifact_hash(args.path)
    if args.json:
        print(json.dumps(digest.__dict__, indent=2, sort_keys=True))
    else:
        print(digest.ref)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate":
            return _validate(args)
        if args.command == "inspect":
            return _inspect(args)
        if args.command == "hash":
            return _hash(args)
    except (OSError, ArtifactValidationError, ValueError, TypeError) as exc:
        code = getattr(exc, "error_code", type(exc).__name__)
        print(f"Artifact {args.command} failed: {code}: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""CLI for Klein Runbook v1 artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.execution import build_runbook_from_artifact, canonical_runbook_hash, validate_runbook
from klein.execution.validation import load_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein-runbook", description="Build, validate, and hash Runbook v1 artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build")
    build.add_argument("--artifact", type=Path, required=True)
    build.add_argument("--output", type=Path, required=True)
    for name in ("validate", "hash", "inspect"):
        command = subparsers.add_parser(name)
        command.add_argument("path", type=Path)
        command.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            runbook = build_runbook_from_artifact(args.artifact)
            args.output.write_text(json.dumps(runbook, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(f"Runbook written: {args.output}")
            return 0
        data = load_json(args.path)
        if args.command == "validate":
            result = validate_runbook(data)
            if args.json:
                print(json.dumps(result.__dict__, indent=2, sort_keys=True))
            else:
                print("Runbook valid" if result.ok else f"Runbook invalid: {result.error_code}: {result.message}")
            return 0 if result.ok else 1
        if args.command == "hash":
            digest = canonical_runbook_hash(args.path)
            print(json.dumps(digest.__dict__, indent=2, sort_keys=True) if args.json else digest.ref)
            return 0
        if args.command == "inspect":
            digest = canonical_runbook_hash(args.path)
            result = validate_runbook(data)
            payload = {**result.__dict__, "runbook_hash": digest.ref, "planned_step_count": len(data.get("planned_steps", []))}
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else f"Runbook: hash={digest.ref} steps={payload['planned_step_count']}")
            return 0 if result.ok else 1
    except Exception as exc:
        print(f"runbook command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

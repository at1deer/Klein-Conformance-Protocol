"""CLI for Klein Execution Trace v1 artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.execution import canonical_trace_hash, compare_trace_to_runbook, validate_execution_trace
from klein.execution.validation import load_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein-trace", description="Validate, hash, and compare Execution Trace v1 artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "hash", "inspect"):
        command = subparsers.add_parser(name)
        command.add_argument("path", type=Path)
        command.add_argument("--json", action="store_true")
    compare = subparsers.add_parser("compare")
    compare.add_argument("--runbook", type=Path, required=True)
    compare.add_argument("--trace", type=Path, required=True)
    compare.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "compare":
            result = compare_trace_to_runbook(load_json(args.trace), load_json(args.runbook))
            if args.json:
                print(json.dumps(result.__dict__, indent=2, sort_keys=True))
            else:
                print("Trace matches runbook" if result.ok else f"Trace mismatch: {result.error_code}: {result.message}")
            return 0 if result.ok else 1
        data = load_json(args.path)
        if args.command == "validate":
            result = validate_execution_trace(data)
            print(json.dumps(result.__dict__, indent=2, sort_keys=True) if args.json else ("Trace valid" if result.ok else f"Trace invalid: {result.error_code}: {result.message}"))
            return 0 if result.ok else 1
        if args.command == "hash":
            digest = canonical_trace_hash(args.path)
            print(json.dumps(digest.__dict__, indent=2, sort_keys=True) if args.json else digest.ref)
            return 0
        if args.command == "inspect":
            digest = canonical_trace_hash(args.path)
            result = validate_execution_trace(data)
            payload = {**result.__dict__, "trace_hash": digest.ref, "trace_step_count": len(data.get("trace_steps", []))}
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else f"Trace: hash={digest.ref} steps={payload['trace_step_count']}")
            return 0 if result.ok else 1
    except Exception as exc:
        print(f"trace command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

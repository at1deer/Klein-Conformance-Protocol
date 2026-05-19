"""CLI for Recorded Device Run v1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.recording import (
    canonical_recorded_run_hash,
    create_mock_recorded_run,
    inspect_recorded_run,
    load_recorded_run_json,
    validate_raw_device_log_jsonl,
    validate_recorded_run_package,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein-recorded-run", description="Validate Recorded Device Run v1 archives.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("path", type=Path)
    validate.add_argument("--verify-bundle", action="store_true")
    inspect = subparsers.add_parser("inspect")
    inspect.add_argument("path", type=Path)
    hash_cmd = subparsers.add_parser("hash")
    hash_cmd.add_argument("path", type=Path)
    raw = subparsers.add_parser("validate-raw-log")
    raw.add_argument("path", type=Path)
    create = subparsers.add_parser("create-mock")
    create.add_argument("--bundle", type=Path, required=True)
    create.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = validate_recorded_run_package(args.path, verify_bundle=args.verify_bundle)
            return _emit_validation(args.path, result)
        if args.command == "inspect":
            data = _load_from_path(args.path)
            print(json.dumps(inspect_recorded_run(data), indent=2, sort_keys=True))
            return 0
        if args.command == "hash":
            data = _load_from_path(args.path)
            print(canonical_recorded_run_hash(data).ref)
            return 0
        if args.command == "validate-raw-log":
            result = validate_raw_device_log_jsonl(args.path)
            if result.ok:
                print(f"Raw Device Log valid events={result.details.get('event_count', 0)}")
                return 0
            print(f"Raw Device Log invalid: {result.error_code}: {result.message}", file=sys.stderr)
            return 1
        if args.command == "create-mock":
            output = create_mock_recorded_run(args.bundle, args.output)
            print(f"Created mock Recorded Device Run v1 at {output}")
            print("hardware_claimed=false attestation_status=absent trusted_timestamp_status=absent")
            return 0
    except Exception as exc:
        print(f"Recorded run command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1


def _load_from_path(path: Path) -> dict:
    target = path / "recorded_run.json" if path.is_dir() else path
    return load_recorded_run_json(target)


def _emit_validation(path: Path, result: object) -> int:
    if getattr(result, "ok", False):
        details = getattr(result, "details", {})
        print(f"Recorded Device Run valid: {path}")
        print(f"  source_type={_source_type(path)}")
        print("  hardware_claimed=false")
        print("  attestation_status=absent")
        print("  trusted_timestamp_status=absent")
        print("  strict_current_alpha=pass")
        if details:
            print(f"  bundle_verification_status={details.get('bundle_verification_status', 'not_requested')}")
            print(f"  raw_log_status={details.get('raw_log_status', 'pass')}")
        return 0
    print(f"Recorded Device Run invalid: {getattr(result, 'error_code', None)}: {getattr(result, 'message', None)}", file=sys.stderr)
    return 1


def _source_type(path: Path) -> str:
    try:
        return str(_load_from_path(path).get("source_type"))
    except Exception:
        return "unknown"


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

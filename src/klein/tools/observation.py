"""CLI for Observation Snapshot v1 validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.execution import (
    canonical_observation_hash,
    compare_observation_to_runbook,
    compare_observation_to_trace,
    load_observation_json,
    validate_observation_contract,
    validate_observation_policy,
    validate_observation_snapshot,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein-observation", description="Validate Observation v1 artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    policy = subparsers.add_parser("validate-policy")
    policy.add_argument("path", type=Path)
    policy.add_argument("--json", action="store_true")
    snapshot = subparsers.add_parser("validate-snapshot")
    snapshot.add_argument("path", type=Path)
    snapshot.add_argument("--json", action="store_true")
    hash_cmd = subparsers.add_parser("hash")
    hash_cmd.add_argument("path", type=Path)
    trace = subparsers.add_parser("compare-trace")
    trace.add_argument("--observation", type=Path, required=True)
    trace.add_argument("--trace", type=Path, required=True)
    trace.add_argument("--json", action="store_true")
    runbook = subparsers.add_parser("compare-runbook")
    runbook.add_argument("--observation", type=Path, required=True)
    runbook.add_argument("--runbook", type=Path, required=True)
    runbook.add_argument("--json", action="store_true")
    contract = subparsers.add_parser("validate-contract")
    contract.add_argument("--policy", type=Path, required=True)
    contract.add_argument("--observation", type=Path, action="append", required=True)
    contract.add_argument("--trace", type=Path, required=True)
    contract.add_argument("--runbook", type=Path, required=True)
    contract.add_argument("--recovery-success", action="store_true")
    contract.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-policy":
            return _emit("Observation policy valid", validate_observation_policy(load_observation_json(args.path)), args.json)
        if args.command == "validate-snapshot":
            return _emit("Observation snapshot valid", validate_observation_snapshot(load_observation_json(args.path)), args.json)
        if args.command == "hash":
            print(canonical_observation_hash(args.path).ref)
            return 0
        if args.command == "compare-trace":
            result = compare_observation_to_trace(load_observation_json(args.observation), load_observation_json(args.trace))
            return _emit("Observation matches trace", result, args.json)
        if args.command == "compare-runbook":
            result = compare_observation_to_runbook(load_observation_json(args.observation), load_observation_json(args.runbook))
            return _emit("Observation matches runbook", result, args.json)
        if args.command == "validate-contract":
            observations = [load_observation_json(path) for path in args.observation]
            result = validate_observation_contract(
                observations,
                load_observation_json(args.trace),
                load_observation_json(args.runbook),
                load_observation_json(args.policy),
                recovery_success=args.recovery_success,
            )
            return _emit("Observation contract valid", result, args.json)
    except Exception as exc:
        print(f"Observation command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1


def _emit(message: str, result: object, as_json: bool) -> int:
    ok = bool(getattr(result, "ok", False))
    if as_json:
        print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    else:
        print(message if ok else f"Observation invalid: {getattr(result, 'error_code', None)}: {getattr(result, 'message', None)}")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

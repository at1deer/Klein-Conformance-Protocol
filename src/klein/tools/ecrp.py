"""CLI for ECRP Retry/Replan Contract v1 validation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.execution import (
    canonical_ecrp_policy_hash,
    load_ecrp_policy,
    validate_ecrp_attempt_sequence,
    validate_ecrp_policy,
    validate_trace_recovery_contract,
)
from klein.execution.validation import load_json
from klein.hail.validation import parse_jsonl_events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein-ecrp", description="Validate ECRP Contract v1 policies and evidence.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    policy = subparsers.add_parser("validate-policy")
    policy.add_argument("path", type=Path)
    policy.add_argument("--json", action="store_true")
    inspect = subparsers.add_parser("inspect-policy")
    inspect.add_argument("path", type=Path)
    inspect.add_argument("--json", action="store_true")
    hail = subparsers.add_parser("validate-hail")
    hail.add_argument("--hail", type=Path, required=True)
    hail.add_argument("--policy", type=Path, required=True)
    hail.add_argument("--json", action="store_true")
    trace = subparsers.add_parser("validate-trace")
    trace.add_argument("--trace", type=Path, required=True)
    trace.add_argument("--runbook", type=Path, required=True)
    trace.add_argument("--policy", type=Path, required=True)
    trace.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "validate-policy":
            policy = load_json(args.path)
            result = validate_ecrp_policy(policy)
            return _emit("ECRP policy valid", result, args.json)
        if args.command == "inspect-policy":
            policy = load_ecrp_policy(args.path)
            digest = canonical_ecrp_policy_hash(policy)
            payload = {"ok": True, "policy_id": policy.get("policy_id"), "policy_hash": digest.ref}
            print(json.dumps(payload, indent=2, sort_keys=True) if args.json else f"ECRP policy: id={payload['policy_id']} hash={digest.ref}")
            return 0
        if args.command == "validate-hail":
            policy = load_ecrp_policy(args.policy)
            validation, events = parse_jsonl_events(args.hail.read_text(encoding="utf-8"))
            if not validation.ok:
                print(f"HAIL invalid: {validation.error_code}: {validation.message}", file=sys.stderr)
                return 1
            result = validate_ecrp_attempt_sequence(events, policy)
            return _emit("ECRP HAIL contract valid", result, args.json)
        if args.command == "validate-trace":
            trace = load_json(args.trace)
            result = validate_trace_recovery_contract(trace, load_json(args.runbook), load_ecrp_policy(args.policy))
            message = "ECRP trace contract valid"
            if trace.get("metadata", {}).get("ecrp_recovery_status") == "success":
                message = "ECRP trace contract valid recovery_status=success"
            return _emit(message, result, args.json)
    except Exception as exc:
        print(f"ECRP command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1


def _emit(message: str, result: object, as_json: bool) -> int:
    ok = bool(getattr(result, "ok", False))
    if as_json:
        print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    else:
        print(message if ok else f"ECRP contract invalid: {getattr(result, 'error_code', None)}: {getattr(result, 'message', None)}")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

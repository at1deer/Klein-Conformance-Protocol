"""CLI for HIL Readiness v1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.hil import (
    MockHilBackend,
    canonical_hil_contract_hash,
    load_hil_json,
    validate_hil_backend_contract,
    validate_hil_backend_status,
)
from klein.substrate.api import Frame


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein-hil", description="Validate HIL Readiness v1 contracts and mock operations.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_contract = subparsers.add_parser("validate-contract")
    validate_contract.add_argument("path", type=Path)
    validate_contract.add_argument("--json", action="store_true")
    validate_status = subparsers.add_parser("validate-status")
    validate_status.add_argument("path", type=Path)
    validate_status.add_argument("--json", action="store_true")
    inspect_contract = subparsers.add_parser("inspect-contract")
    inspect_contract.add_argument("path", type=Path)
    subparsers.add_parser("mock-health")
    subparsers.add_parser("mock-estop")
    subparsers.add_parser("mock-reset")
    apply = subparsers.add_parser("mock-apply-frame")
    apply.add_argument("path", type=Path, nargs="?")
    subparsers.add_parser("mock-observe")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-contract":
            result = validate_hil_backend_contract(load_hil_json(args.path))
            return _emit("HIL contract valid (interface readiness only)", result, args.json)
        if args.command == "validate-status":
            result = validate_hil_backend_status(load_hil_json(args.path))
            return _emit("HIL status valid", result, args.json)
        if args.command == "inspect-contract":
            contract = load_hil_json(args.path)
            result = validate_hil_backend_contract(contract)
            if not result.ok:
                return _emit("HIL contract valid", result, False)
            print(f"HIL contract: backend_id={contract['backend_id']} hash={canonical_hil_contract_hash(contract).ref} physical_hardware=false")
            return 0
        backend = MockHilBackend()
        if args.command == "mock-health":
            print(json.dumps(backend.get_health(), indent=2, sort_keys=True))
            return 0
        if args.command == "mock-estop":
            print(json.dumps(backend.emergency_stop(), indent=2, sort_keys=True))
            return 0
        if args.command == "mock-reset":
            print(json.dumps(backend.reset(), indent=2, sort_keys=True))
            return 0
        if args.command == "mock-apply-frame":
            frame = _frame_from_path(args.path) if args.path else Frame(seq=1, active_electrodes=(1, 2), duration_ms=10)
            ack = backend.apply_frame(frame)
            print(json.dumps({"ok": ack.ok, "seq": ack.seq, "mock": True, "physical_hardware": False}, indent=2, sort_keys=True))
            return 0 if ack.ok else 1
        if args.command == "mock-observe":
            backend.apply_frame(Frame(seq=1, active_electrodes=(1, 2), duration_ms=10))
            print(json.dumps(backend.read_observation(), indent=2, sort_keys=True))
            return 0
    except Exception as exc:
        print(f"HIL command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1


def _frame_from_path(path: Path) -> Frame:
    data = json.loads(path.read_text(encoding="utf-8"))
    return Frame(
        seq=int(data.get("seq", 1)),
        active_electrodes=tuple(int(value) for value in data.get("active_electrodes", [])),
        duration_ms=int(data.get("duration_ms", 10)),
    )


def _emit(message: str, result: object, as_json: bool) -> int:
    ok = bool(getattr(result, "ok", False))
    if as_json:
        print(json.dumps(result.__dict__, indent=2, sort_keys=True))
    else:
        print(message if ok else f"HIL invalid: {getattr(result, 'error_code', None)}: {getattr(result, 'message', None)}")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

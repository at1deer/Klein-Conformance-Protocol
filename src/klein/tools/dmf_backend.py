"""CLI for Generic DMF Backend Adapter v1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.backends.dmf import (
    GenericDmfDryRunAdapter,
    load_dmf_backend_adapter_config,
    validate_dmf_backend_adapter_config,
    validate_dmf_backend_adapter_status,
)
from klein.common.hashing import parse_ijson


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein-dmf-backend", description="Validate and run Generic DMF Backend Adapter v1 dry-run skeletons.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_config = subparsers.add_parser("validate-config")
    validate_config.add_argument("path", type=Path)
    validate_status = subparsers.add_parser("validate-status")
    validate_status.add_argument("path", type=Path)
    inspect_config = subparsers.add_parser("inspect-config")
    inspect_config.add_argument("path", type=Path)
    dry_run = subparsers.add_parser("dry-run-runbook")
    dry_run.add_argument("--config", type=Path, required=True)
    dry_run.add_argument("--runbook", type=Path, required=True)
    dry_run.add_argument("--output", type=Path, required=True)
    recording = subparsers.add_parser("create-mock-recording")
    recording.add_argument("--config", type=Path, required=True)
    recording.add_argument("--runbook", type=Path, required=True)
    recording.add_argument("--bundle", type=Path, required=True)
    recording.add_argument("--output", type=Path, required=True)
    estop = subparsers.add_parser("estop")
    estop.add_argument("--config", type=Path, required=True)
    reset = subparsers.add_parser("reset")
    reset.add_argument("--config", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate-config":
            result = validate_dmf_backend_adapter_config(load_dmf_backend_adapter_config(args.path))
            return _emit("DMF backend adapter config valid (dry-run only)", result)
        if args.command == "validate-status":
            data = parse_ijson(args.path.read_text(encoding="utf-8"))
            result = validate_dmf_backend_adapter_status(data)
            return _emit("DMF backend adapter status valid", result)
        if args.command == "inspect-config":
            config = load_dmf_backend_adapter_config(args.path)
            result = validate_dmf_backend_adapter_config(config)
            if not result.ok:
                return _emit("DMF backend adapter config valid", result)
            print(json.dumps({
                "adapter_id": config["adapter_id"],
                "backend_id": config["backend_id"],
                "mode": config["mode"],
                "hardware_io_enabled": config["hardware_io_enabled"],
                "profile": config["profile"],
                "dry_run_only": True,
                "physical_execution": False,
            }, indent=2, sort_keys=True))
            return 0
        if args.command == "dry-run-runbook":
            adapter = GenericDmfDryRunAdapter(load_dmf_backend_adapter_config(args.config))
            result = adapter.run_runbook_dry(_load_runbook(args.runbook), output_dir=args.output)
            if not result.ok:
                print(f"DMF dry-run failed: {result.error_code}: {result.message}", file=sys.stderr)
                return 1
            print(f"DMF dry-run complete: {args.output}")
            print("hardware_io_enabled=false physical_execution=false")
            print(f"trace_steps={len(result.trace['trace_steps'])} raw_events={len(result.raw_events)} observations={len(result.observations)}")
            return 0
        if args.command == "create-mock-recording":
            adapter = GenericDmfDryRunAdapter(load_dmf_backend_adapter_config(args.config))
            result = adapter.run_runbook_dry(_load_runbook(args.runbook))
            adapter.create_recorded_run_from_adapter_result(result, bundle_path=args.bundle, output_dir=args.output)
            print(f"DMF mock recorded-run package created: {args.output}")
            print("dry_run_only=true hardware_io_enabled=false physical_execution=false")
            return 0
        if args.command == "estop":
            adapter = GenericDmfDryRunAdapter(load_dmf_backend_adapter_config(args.config))
            print(json.dumps(adapter.emergency_stop(), indent=2, sort_keys=True))
            return 0
        if args.command == "reset":
            adapter = GenericDmfDryRunAdapter(load_dmf_backend_adapter_config(args.config))
            print(json.dumps(adapter.reset(), indent=2, sort_keys=True))
            return 0
    except Exception as exc:
        print(f"DMF backend command failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 1


def _load_runbook(path: Path) -> dict:
    data = parse_ijson(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("runbook must be a JSON object")
    return data


def _emit(message: str, result: object) -> int:
    ok = bool(getattr(result, "ok", False))
    print(message if ok else f"DMF backend adapter invalid: {getattr(result, 'error_code', None)}: {getattr(result, 'message', None)}")
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

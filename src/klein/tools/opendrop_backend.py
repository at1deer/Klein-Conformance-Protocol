"""CLI for the OpenDrop/EWOD dry-run adapter skeleton."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from klein.backends.dmf.opendrop import (
    OpenDropAdapterError,
    OpenDropEwodDryRunAdapter,
    inspect_transport_config,
    load_opendrop_adapter_config,
    load_opendrop_transport_config,
    runbook_step_to_opendrop_intent,
    serialize_intents_to_command_stream,
    validate_opendrop_adapter_config,
    validate_opendrop_adapter_status,
    validate_opendrop_transport_config,
)
from klein.common.hashing import parse_ijson


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="klein-opendrop-backend", description="OpenDrop/EWOD dry-run skeleton CLI. No physical execution.")
    sub = parser.add_subparsers(dest="command", required=True)
    _path_cmd(sub, "validate-config", "Validate OpenDrop/EWOD adapter config")
    _path_cmd(sub, "validate-status", "Validate OpenDrop/EWOD adapter status")
    _path_cmd(sub, "inspect-config", "Inspect OpenDrop/EWOD adapter config")
    _path_cmd(sub, "validate-transport", "Validate OpenDrop transport planning config")
    _path_cmd(sub, "inspect-transport", "Inspect OpenDrop transport planning config")
    _path_cmd(sub, "map-electrodes", "Map OpenDrop/EWOD electrodes")
    serialize_intents = sub.add_parser("serialize-intents", help="Serialize OpenDrop command intents to a dry-run command stream")
    serialize_intents.add_argument("--transport", required=True)
    serialize_intents.add_argument("--intents", required=True)
    serialize_intents.add_argument("--output", required=True)
    serialize_runbook = sub.add_parser("serialize-runbook", help="Serialize a DMF runbook to an OpenDrop dry-run command stream")
    serialize_runbook.add_argument("--config", required=True)
    serialize_runbook.add_argument("--transport", required=True)
    serialize_runbook.add_argument("--runbook", required=True)
    serialize_runbook.add_argument("--output", required=True)
    dry = sub.add_parser("dry-run-runbook", help="Generate OpenDrop/EWOD dry-run outputs")
    dry.add_argument("--config", required=True)
    dry.add_argument("--runbook", required=True)
    dry.add_argument("--output", required=True)
    rec = sub.add_parser("create-mock-recording", help="Generate OpenDrop/EWOD mock recorded-run package")
    rec.add_argument("--config", required=True)
    rec.add_argument("--runbook", required=True)
    rec.add_argument("--bundle", required=True)
    rec.add_argument("--output", required=True)
    _path_cmd(sub, "estop", "Exercise dry-run emergency stop")
    _path_cmd(sub, "reset", "Exercise dry-run reset")
    args = parser.parse_args(argv)
    try:
        return _dispatch(args)
    except OpenDropAdapterError as exc:
        print(f"{exc.error_code}: {exc}", file=sys.stderr)
        return 1


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "validate-config":
        config = load_opendrop_adapter_config(args.path)
        result = validate_opendrop_adapter_config(config)
        if not result.ok:
            print(f"{result.error_code}: {result.message}", file=sys.stderr)
            return 1
        print("OpenDrop/EWOD dry-run skeleton config valid: hardware_io_enabled=false; no physical execution")
        return 0
    if args.command == "validate-status":
        status = _load_json(args.path)
        result = validate_opendrop_adapter_status(status)
        if not result.ok:
            print(f"{result.error_code}: {result.message}", file=sys.stderr)
            return 1
        print("OpenDrop/EWOD dry-run skeleton status valid: hardware_io_enabled=false; no physical execution")
        return 0
    if args.command == "inspect-config":
        config = load_opendrop_adapter_config(args.path)
        result = validate_opendrop_adapter_config(config)
        if not result.ok:
            print(f"{result.error_code}: {result.message}", file=sys.stderr)
            return 1
        layout = config["electrode_layout"]
        print(f"OpenDrop/EWOD dry-run skeleton: {config['adapter_id']}")
        print("hardware_io_enabled=false; no physical execution")
        print(f"layout={layout['layout_id']} grid={layout['grid_width']}x{layout['grid_height']} channels={layout['channel_count']} mapping={layout['mapping']}")
        return 0
    if args.command == "validate-transport":
        transport = load_opendrop_transport_config(args.path)
        result = validate_opendrop_transport_config(transport)
        if not result.ok:
            print(f"{result.error_code}: {result.message}", file=sys.stderr)
            print("OpenDrop hardware transport is intentionally disabled in CURRENT_ALPHA.", file=sys.stderr)
            return 1
        print("OpenDrop transport planning config valid: hardware_io_enabled=false; serialized command stream only; no device IO performed")
        return 0
    if args.command == "inspect-transport":
        transport = load_opendrop_transport_config(args.path)
        inspection = inspect_transport_config(transport)
        print(f"OpenDrop transport: kind={inspection.transport_kind} status={inspection.transport_status}")
        print(inspection.message)
        if inspection.transport_status == "invalid":
            return 1
        return 0
    if args.command == "map-electrodes":
        config = load_opendrop_adapter_config(args.path)
        adapter = OpenDropEwodDryRunAdapter(config)
        rows = [electrode.__dict__ for _, electrode in sorted(adapter.mapping.items())]
        print(json.dumps({"adapter": "OpenDrop/EWOD dry-run skeleton", "hardware_io_enabled": False, "electrodes": rows}, indent=2, sort_keys=True))
        return 0
    if args.command == "serialize-intents":
        transport = load_opendrop_transport_config(args.transport)
        intents = _load_json_or_jsonl(args.intents)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialize_intents_to_command_stream(intents, transport), encoding="utf-8")
        print(f"OpenDrop dry-run command stream serialized: {output}")
        print("serialized command stream only; hardware_io_enabled=false; no device IO performed")
        return 0
    if args.command == "serialize-runbook":
        config = load_opendrop_adapter_config(args.config)
        transport = load_opendrop_transport_config(args.transport)
        runbook = _load_json(args.runbook)
        intents = _intents_from_runbook(config, runbook)
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialize_intents_to_command_stream(intents, transport), encoding="utf-8")
        print(f"OpenDrop dry-run command stream serialized from runbook: {output}")
        print("serialized command stream only; hardware_io_enabled=false; no device IO performed")
        return 0
    if args.command == "dry-run-runbook":
        config = load_opendrop_adapter_config(args.config)
        runbook = _load_json(args.runbook)
        output = Path(args.output)
        _prepare_empty_output(output)
        result = OpenDropEwodDryRunAdapter(config).run_runbook_dry(runbook, output_dir=output)
        if not result.ok:
            print(f"{result.error_code}: {result.message}", file=sys.stderr)
            return 1
        print(f"OpenDrop/EWOD dry-run skeleton complete: {output}")
        print("hardware_io_enabled=false; no physical execution")
        return 0
    if args.command == "create-mock-recording":
        config = load_opendrop_adapter_config(args.config)
        runbook = _load_json(args.runbook)
        output = Path(args.output)
        _prepare_empty_output(output)
        adapter = OpenDropEwodDryRunAdapter(config)
        result = adapter.run_runbook_dry(runbook)
        adapter.create_recorded_run_from_adapter_result(result, bundle_path=args.bundle, output_dir=output)
        print(f"OpenDrop/EWOD mock recorded-run package created: {output}")
        print("hardware_io_enabled=false; no physical execution")
        return 0
    if args.command == "estop":
        adapter = OpenDropEwodDryRunAdapter(load_opendrop_adapter_config(args.path))
        print(json.dumps(adapter.emergency_stop(), indent=2, sort_keys=True))
        print("OpenDrop/EWOD dry-run skeleton emergency stop active")
        return 0
    if args.command == "reset":
        adapter = OpenDropEwodDryRunAdapter(load_opendrop_adapter_config(args.path))
        adapter.emergency_stop()
        print(json.dumps(adapter.reset(), indent=2, sort_keys=True))
        print("OpenDrop/EWOD dry-run skeleton reset")
        return 0
    raise AssertionError(f"unknown command: {args.command}")


def _path_cmd(sub: argparse._SubParsersAction[argparse.ArgumentParser], name: str, help_text: str) -> None:
    cmd = sub.add_parser(name, help=help_text)
    cmd.add_argument("path")


def _load_json(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise OpenDropAdapterError("OPENDROP_ADAPTER_SCHEMA_INVALID", "JSON root must be an object")
    return data


def _load_json_or_jsonl(path: str | Path) -> list[dict[str, Any]]:
    source = Path(path)
    text = source.read_text(encoding="utf-8")
    if source.suffix == ".jsonl":
        rows = [parse_ijson(line) for line in text.splitlines() if line.strip()]
        if not all(isinstance(row, dict) for row in rows):
            raise OpenDropAdapterError("OPENDROP_COMMAND_INTENT_INVALID", "JSONL intents must contain objects")
        return rows
    data = parse_ijson(text)
    if isinstance(data, dict):
        data = data.get("intents", [data])
    if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
        raise OpenDropAdapterError("OPENDROP_COMMAND_INTENT_INVALID", "intents must be an object, array, or JSONL objects")
    return data


def _intents_from_runbook(config: dict[str, Any], runbook: dict[str, Any]) -> list[dict[str, Any]]:
    adapter = OpenDropEwodDryRunAdapter(config)
    return [
        runbook_step_to_opendrop_intent(step, adapter.mapping, adapter._electrical_context(step), seq=index)
        for index, step in enumerate(runbook.get("planned_steps", []), start=1)
    ]


def _prepare_empty_output(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)


if __name__ == "__main__":
    raise SystemExit(main())

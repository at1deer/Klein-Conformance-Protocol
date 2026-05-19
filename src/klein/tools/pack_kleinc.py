#!/usr/bin/env python3
"""
Klein Container Packing Tool (pack-kleinc)

Packs a folder of loose test vector files into a single .kleinc container file.
This simplifies contribution workflows and ensures consistency.

Usage:
    python tools/pack_kleinc.py <input_folder> [output.kleinc]
    python tools/pack_kleinc.py tests/vectors/loose/001_minimal_muxed -o tests/vectors/kap/001.kleinc

Folder Structure Expected:
    input_folder/
        manifest.json       # Required: package manifest
        payload.json        # OR payload.csv - actuation data
        simgb.json         # Optional: State Image Bundle (formerly dsb.json)
        runbook.json       # Optional: execution runbook
        expected/
            expected.json  # Optional: conformance expectations
        golden/
            observables.jsonl  # Optional: golden output

Output:
    A single .kleinc JSON file containing all components.

Note:
    This tool also accepts legacy dsb.json files and will include them
    in the container for backwards compatibility.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

try:
    from klein.common.models import Container
    HAVE_MODELS = True
except ImportError:
    HAVE_MODELS = False


# =============================================================================
# Constants
# =============================================================================

CONTAINER_VERSION = "1.0"

DEFAULT_MANIFEST = {
    "project": {
        "name": "unnamed",
        "version": "1.0.0",
        "authors": ["unknown"],
        "license": "MIT"
    },
    "runtime": {
        "mode": "HARD",
        "target_substrate": "dmf.muxed_ewod.opendrop.v1.0"
    }
}


# =============================================================================
# Utilities
# =============================================================================

def compute_sha256(data: str | bytes) -> str:
    """Compute SHA256 hash of data."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    """Load a JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file."""
    result = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                result.append(json.loads(line))
    return result


def load_csv_payload(path: Path) -> list[dict[str, Any]]:
    """Load a CSV payload file into list of records."""
    result = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Convert numeric fields
            record = {}
            for key, value in row.items():
                if value.isdigit():
                    record[key] = int(value)
                else:
                    try:
                        record[key] = float(value)
                    except ValueError:
                        record[key] = value
            result.append(record)
    return result


def detect_payload_kind(data: list[dict[str, Any]]) -> str:
    """Detect payload kind from data structure."""
    if not data:
        return "CHANNEL_LIST"

    sample = data[0]

    if "channel_id" in sample or "voltage_v" in sample:
        return "CHANNEL_LIST"
    elif "active" in sample or "pixels" in sample:
        return "FRAME_SEQUENCE"
    elif "bitmap" in sample:
        return "BITMAP_SEQUENCE"
    else:
        return "CHANNEL_LIST"


# =============================================================================
# Packing Logic
# =============================================================================

def pack_folder(folder: Path, output: Path | None = None, validate: bool = True) -> dict[str, Any]:
    """
    Pack a folder of loose files into a .kleinc container.

    Args:
        folder: Path to input folder
        output: Path to output .kleinc file (optional)
        validate: Whether to validate against Pydantic models

    Returns:
        The container dict
    """
    folder = Path(folder)
    if not folder.is_dir():
        raise ValueError(f"Not a directory: {folder}")

    print(f"Packing: {folder}")

    # Load manifest
    manifest_path = folder / "manifest.json"
    if manifest_path.exists():
        manifest = load_json(manifest_path)
        print("  Loaded manifest.json")
    else:
        # Try to infer from folder name
        folder_name = folder.name
        manifest = DEFAULT_MANIFEST.copy()
        manifest["project"] = manifest["project"].copy()
        manifest["project"]["name"] = folder_name
        manifest["project"]["description"] = f"Auto-generated from {folder_name}"
        print("  Using default manifest (no manifest.json found)")

    # Load payload
    payload_data = None
    payload_kind = None
    payload_encoding = "JSON"

    for payload_file in ["payload.json", "payload.jsonl", "payload.csv"]:
        payload_path = folder / payload_file
        if payload_path.exists():
            if payload_file.endswith(".json"):
                payload_data = load_json(payload_path)
                if not isinstance(payload_data, list):
                    payload_data = [payload_data]
            elif payload_file.endswith(".jsonl"):
                payload_data = load_jsonl(payload_path)
            elif payload_file.endswith(".csv"):
                payload_data = load_csv_payload(payload_path)

            payload_kind = detect_payload_kind(payload_data)
            print(f"  Loaded {payload_file} ({len(payload_data)} records)")
            break

    if payload_data is None:
        # Check for alternative payload formats
        for alt in ["frames.json", "channels.json", "actuations.json"]:
            alt_path = folder / alt
            if alt_path.exists():
                payload_data = load_json(alt_path)
                if not isinstance(payload_data, list):
                    payload_data = [payload_data]
                payload_kind = detect_payload_kind(payload_data)
                print(f"  Loaded {alt} ({len(payload_data)} records)")
                break

    if payload_data is None:
        # Minimal empty payload
        payload_data = []
        payload_kind = "CHANNEL_LIST"
        print("  No payload found, using empty CHANNEL_LIST")

    # Build container
    container: dict[str, Any] = {
        "klein_container_version": CONTAINER_VERSION,
        "manifest": manifest,
        "payload": {
            "kind": payload_kind,
            "data": payload_data,
            "encoding": payload_encoding
        }
    }

    # Load optional SImgB (or legacy DSB)
    simgb_path = folder / "simgb.json"
    dsb_path = folder / "dsb.json"
    if simgb_path.exists():
        container["simgb"] = load_json(simgb_path)
        print("  Loaded simgb.json")
    elif dsb_path.exists():
        # Legacy support: load dsb.json into both fields for compatibility
        dsb_data = load_json(dsb_path)
        container["simgb"] = dsb_data
        container["dsb"] = dsb_data  # Legacy field for backwards compat
        print("  Loaded dsb.json (legacy, mapped to simgb)")

    # Load optional runbook
    runbook_path = folder / "runbook.json"
    if runbook_path.exists():
        container["runbook"] = load_json(runbook_path)
        print("  Loaded runbook.json")

    # Validate if models available
    if validate and HAVE_MODELS:
        try:
            Container.model_validate(container)
            print("  Validated against Container schema")
        except Exception as e:
            print(f"  WARNING: Validation failed: {e}")

    # Write output
    if output is None:
        output = folder.with_suffix(".kleinc")

    output = Path(output)
    with open(output, "w", encoding="utf-8") as f:
        json.dump(container, f, indent=2)

    print(f"  Written: {output}")
    print(f"  Size: {output.stat().st_size:,} bytes")

    return container


def pack_all_loose(
    loose_dir: Path,
    output_dir: Path,
    validate: bool = True
) -> list[Path]:
    """
    Pack all loose folders in a directory.

    Args:
        loose_dir: Directory containing loose vector folders
        output_dir: Directory to write .kleinc files
        validate: Whether to validate against Pydantic models

    Returns:
        List of created .kleinc file paths
    """
    loose_dir = Path(loose_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    created = []

    for folder in sorted(loose_dir.iterdir()):
        if not folder.is_dir():
            continue

        # Skip hidden folders and special folders
        if folder.name.startswith(".") or folder.name in ("expected", "golden"):
            continue

        output_file = output_dir / f"{folder.name}.kleinc"

        try:
            pack_folder(folder, output_file, validate)
            created.append(output_file)
        except Exception as e:
            print(f"  ERROR packing {folder.name}: {e}")

    return created


# =============================================================================
# CLI
# =============================================================================

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="pack-kleinc",
        description="Pack loose test vector files into .kleinc containers",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Pack a single folder
    python tools/pack_kleinc.py tests/vectors/loose/001_minimal_muxed

    # Pack with custom output path
    python tools/pack_kleinc.py input_folder -o output.kleinc

    # Pack all loose folders in a directory
    python tools/pack_kleinc.py tests/vectors/loose --all -o tests/vectors/kap

    # Skip validation
    python tools/pack_kleinc.py input_folder --no-validate
        """,
    )

    parser.add_argument(
        "input",
        type=Path,
        help="Input folder (or directory of folders with --all)",
    )

    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=None,
        help="Output .kleinc file or directory (with --all)",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Pack all subfolders in input directory",
    )

    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="Skip Pydantic model validation",
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Minimal output",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    try:
        if args.all:
            # Pack all folders
            output_dir = args.output or args.input.parent / "kap"
            created = pack_all_loose(args.input, output_dir, not args.no_validate)
            if not args.quiet:
                print(f"\nPacked {len(created)} containers to {output_dir}")
        else:
            # Pack single folder
            pack_folder(args.input, args.output, not args.no_validate)

        return 0

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

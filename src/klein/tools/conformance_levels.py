"""CLI for KCP Conformance Levels Matrix v1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.conformance.levels import (
    ConformanceLevelError,
    get_conformance_level,
    load_conformance_level_catalog,
    validate_conformance_level_catalog,
    verify_capability_declared_levels,
)
from klein.crypto.capabilities import BackendCapabilityError, load_backend_capability_declaration


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="klein-conformance-levels",
        description="Inspect and validate KCP Conformance Levels Matrix v1.",
    )
    parser.add_argument("--catalog", type=Path, help="Optional conformance level catalog path.")
    parser.add_argument("--json", action="store_true", help="Emit JSON output.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="List known conformance levels.")
    show = subparsers.add_parser("show", help="Show one conformance level.")
    show.add_argument("level_id")
    subparsers.add_parser("validate-catalog", help="Validate the conformance-level catalog.")
    verify = subparsers.add_parser("verify-capabilities", help="Verify declaration level claims.")
    verify.add_argument("--declaration", type=Path, required=True)
    verify.add_argument("--allow-target-claims", action="store_true")
    return parser


def _load(args: argparse.Namespace) -> dict:
    return load_conformance_level_catalog(args.catalog)


def _list(args: argparse.Namespace) -> int:
    catalog = _load(args)
    levels = catalog["levels"]
    if args.json:
        print(json.dumps(levels, indent=2, sort_keys=True))
    else:
        for level in levels:
            print(f"{level['level_id']} [{level['status']}/{level['layer']}] - {level['name']}")
    return 0


def _show(args: argparse.Namespace) -> int:
    catalog = _load(args)
    level = get_conformance_level(args.level_id, catalog)
    if args.json:
        print(json.dumps(level, indent=2, sort_keys=True))
    else:
        print(f"{level['level_id']}: {level['name']}")
        print(f"  layer={level['layer']} category={level['category']} status={level['status']}")
        print(f"  requires={', '.join(level['requires']) if level['requires'] else '(none)'}")
        print(f"  forbidden_claims={', '.join(level['forbidden_claims']) if level['forbidden_claims'] else '(none)'}")
    return 0


def _validate_catalog(args: argparse.Namespace) -> int:
    catalog = _load(args)
    validate_conformance_level_catalog(catalog)
    output = {"catalog_version": catalog["catalog_version"], "level_count": len(catalog["levels"]), "status": "pass"}
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(f"Conformance level catalog valid: {output['level_count']} levels")
    return 0


def _verify_capabilities(args: argparse.Namespace) -> int:
    declaration = load_backend_capability_declaration(args.declaration)
    result = verify_capability_declared_levels(
        declaration,
        _load(args),
        allow_target_claims=args.allow_target_claims,
    )
    output = result.__dict__
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(
            "Conformance levels verified: "
            f"catalog_status={result.catalog_status} "
            f"dependency_status={result.dependency_status} "
            f"verified={len(result.verified_levels)}"
        )
    return 0 if result.ok else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "list":
            return _list(args)
        if args.command == "show":
            return _show(args)
        if args.command == "validate-catalog":
            return _validate_catalog(args)
        if args.command == "verify-capabilities":
            return _verify_capabilities(args)
    except (OSError, ConformanceLevelError, BackendCapabilityError) as exc:
        code = getattr(exc, "error_code", type(exc).__name__)
        print(f"Conformance levels failed: {code}: {exc}", file=sys.stderr)
        return 1
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""CLI for KCP Run Bundle v1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.bundle import RunBundleError, create_run_bundle, inspect_run_bundle, verify_run_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="klein-run-bundle", description="Create and verify KCP Run Bundle v1 artifacts.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a .kcprun zip or directory bundle.")
    create.add_argument("--artifact", type=Path, required=True, help="Input artifact path.")
    create.add_argument("--hail", type=Path, required=True, help="HAIL JSONL path.")
    create.add_argument("--manifest", type=Path, required=True, help="Run Manifest v1 path.")
    create.add_argument("--trust-policy", type=Path, required=True, help="Trust Policy v1 path.")
    create.add_argument("--backend-registry", type=Path, help="Optional Backend Identity Registry v1 path.")
    create.add_argument("--backend-capabilities", type=Path, help="Optional Backend Capability Declaration v1 path.")
    create.add_argument("--output", type=Path, required=True, help="Output .kcprun file or directory.")
    create.add_argument("--directory", action="store_true", help="Create directory form instead of .kcprun zip.")
    create.add_argument("--include-conformance-report", type=Path, help="Optional conformance report JSON.")
    create.add_argument(
        "--signed-conformance-report-output",
        action="store_true",
        help="Include generated signed-conformance JSON inside the bundle.",
    )
    create.add_argument("--json", action="store_true", help="Emit stable JSON output.")
    create.set_defaults(func=_create)

    verify = subparsers.add_parser("verify", help="Verify a KCP Run Bundle v1.")
    verify.add_argument("--bundle", type=Path, required=True, help="Bundle directory or .kcprun path.")
    verify.add_argument("--require-signed-registry", action="store_true", help="Require trusted signed registry provenance.")
    verify.add_argument("--require-backend-capabilities", action="store_true", help="Require bundled backend capability declaration.")
    verify.add_argument("--json", action="store_true", help="Emit stable JSON output.")
    verify.set_defaults(func=_verify)

    inspect = subparsers.add_parser("inspect", help="Inspect bundle metadata.")
    inspect.add_argument("--bundle", type=Path, required=True, help="Bundle directory or .kcprun path.")
    inspect.add_argument("--json", action="store_true", help="Emit stable JSON output.")
    inspect.set_defaults(func=_inspect)
    return parser


def _create(args: argparse.Namespace) -> int:
    try:
        output = create_run_bundle(
            artifact_path=args.artifact,
            hail_path=args.hail,
            manifest_path=args.manifest,
            trust_policy_path=args.trust_policy,
            output_path=args.output,
            directory=args.directory,
            conformance_report_path=args.include_conformance_report,
            backend_registry_path=args.backend_registry,
            backend_capabilities_path=args.backend_capabilities,
            include_signed_conformance_report=args.signed_conformance_report_output,
        )
    except RunBundleError as exc:
        print(f"Run Bundle create failed: {exc.error_code}: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps({"created": str(output), "bundle_format": "directory" if args.directory else "zip"}, indent=2, sort_keys=True))
    else:
        print(f"Run Bundle created: {output}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    result = verify_run_bundle(
        args.bundle,
        require_signed_registry=args.require_signed_registry,
        require_backend_capabilities=args.require_backend_capabilities,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Run Bundle verified: overall_status={result.overall_status} format={result.bundle_format}")
        print(f"  bundle_schema_status={result.bundle_schema_status}")
        print(f"  bundle_entry_hash_status={result.bundle_entry_hash_status}")
        print(f"  signed_conformance_status={result.signed_conformance_status}")
        if result.run_manifest_key_ids:
            print(f"  key_ids={','.join(result.run_manifest_key_ids)}")
        print(f"  trust_status={result.trust_status}")
        for error in result.errors:
            print(
                f"  error {error['check']}: {error['error_code']}: {error['message']}",
                file=sys.stderr,
            )
    return 0 if result.ok else 1


def _inspect(args: argparse.Namespace) -> int:
    try:
        info = inspect_run_bundle(args.bundle)
    except RunBundleError as exc:
        print(f"Run Bundle inspect failed: {exc.error_code}: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(info, indent=2, sort_keys=True))
    else:
        print(f"Run Bundle: {info['bundle_path']}")
        print(f"  format: {info['bundle_format']}")
        print(f"  version: {info['bundle'].get('bundle_version')}")
        for key, value in info["bundle"].get("entries", {}).items():
            print(f"  {key}: {value}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

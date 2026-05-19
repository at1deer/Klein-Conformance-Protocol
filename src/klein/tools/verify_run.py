"""CLI reference verifier for KCP-Core-Signed-Conformance-v1."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.verifier import SIGNED_CONFORMANCE_LEVEL, verify_signed_conformance


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="klein-verify-run",
        description="Verify a HAIL stream, manifest, and trust policy as signed-conformant.",
    )
    parser.add_argument("--hail", type=Path, required=True, help="Lifecycle-bound HAIL JSONL.")
    parser.add_argument("--manifest", type=Path, required=True, help="Run Manifest v1 JSON.")
    parser.add_argument("--trust-policy", type=Path, required=True, help="Trust Policy v1 JSON.")
    parser.add_argument("--backend-registry", type=Path, help="Optional Backend Identity Registry v1 JSON.")
    parser.add_argument("--require-signed-registry", action="store_true", help="Require trusted signed registry provenance.")
    parser.add_argument("--artifact", type=Path, help="Optional input artifact to hash-check.")
    parser.add_argument("--conformance-report", type=Path, help="Optional conformance report JSON.")
    parser.add_argument("--json", action="store_true", help="Emit stable JSON verifier output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = verify_signed_conformance(
            hail_path=args.hail,
            manifest_path=args.manifest,
            trust_policy_path=args.trust_policy,
            artifact_path=args.artifact,
            conformance_report_path=args.conformance_report,
            backend_registry_path=args.backend_registry,
            require_signed_registry=args.require_signed_registry,
        )
    except OSError as exc:
        print(f"signed-conformance verification failed: {exc}", file=sys.stderr)
        return 1

    output = result.to_dict()
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(f"{SIGNED_CONFORMANCE_LEVEL}: {result.overall_status}")
        for check, status in output["checks"].items():
            print(f"  {check}: {status}")
        if result.manifest_key_ids:
            print(f"  manifest_key_ids: {','.join(result.manifest_key_ids)}")
        if result.trusted_key_ids:
            print(f"  trusted_key_ids: {','.join(result.trusted_key_ids)}")
        for error in result.errors:
            print(
                f"  error {error['check']}: {error['error_code']}: {error['message']}",
                file=sys.stderr,
            )
    return 0 if result.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

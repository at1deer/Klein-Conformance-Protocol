"""Independent verifier CLI for KCP Run Bundle v1."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from klein.verifier import verify_bundle_independently


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="klein-verify-bundle",
        description="Independently verify a KCP Run Bundle v1 without simulator or vector state.",
    )
    parser.add_argument("bundle", type=Path, help="Bundle directory or .kcprun path.")
    parser.add_argument("--backend-registry", type=Path, help="Optional Backend Identity Registry v1 override.")
    parser.add_argument("--require-signed-registry", action="store_true", help="Require trusted signed registry provenance.")
    parser.add_argument("--require-backend-capabilities", action="store_true", help="Require bundled backend capability declaration.")
    parser.add_argument("--json", action="store_true", help="Emit stable independent verifier JSON.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = verify_bundle_independently(
        args.bundle,
        backend_registry_path=args.backend_registry,
        require_signed_registry=args.require_signed_registry,
        require_backend_capabilities=args.require_backend_capabilities,
    )
    if args.json:
        print(json.dumps(result.to_dict(), indent=2, sort_keys=True))
    else:
        print(f"Independent verifier: overall_status={result.overall_status} format={result.bundle_format}")
        for check, status in result.checks.items():
            print(f"  {check}: {status}")
        trusted = result.bindings.get("trusted_key_ids") or []
        if trusted:
            print(f"  trusted_key_ids: {','.join(trusted)}")
        for error in result.errors:
            print(f"  error {error['check']}: {error['error_code']}: {error['message']}")
    return 0 if result.ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

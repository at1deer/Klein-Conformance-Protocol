"""CLI for Backend Identity Registry v1 inspection and provenance verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.crypto.registry import (
    BackendIdentityRegistryError,
    load_backend_identity_registry,
    verify_backend_registry_signature,
)
from klein.crypto.trust import TrustPolicyError, load_trust_policy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="klein-backend-registry",
        description="Inspect and verify Klein Backend Identity Registry v1 files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="Verify registry schema and signed provenance.")
    verify.add_argument("--registry", type=Path, required=True, help="Backend Identity Registry v1 JSON.")
    verify.add_argument("--trust-policy", type=Path, help="Trust Policy v1 with registry authorities.")
    verify.add_argument("--require-signed-registry", action="store_true", help="Require trusted signed registry provenance.")
    verify.add_argument("--json", action="store_true", help="Emit stable JSON output.")

    inspect = subparsers.add_parser("inspect", help="Inspect registry summary.")
    inspect.add_argument("--registry", type=Path, required=True, help="Backend Identity Registry v1 JSON.")
    inspect.add_argument("--json", action="store_true", help="Emit stable JSON output.")
    return parser


def _verify(args: argparse.Namespace) -> int:
    try:
        registry = load_backend_identity_registry(args.registry)
        policy = load_trust_policy(args.trust_policy) if args.trust_policy else None
        result = verify_backend_registry_signature(
            registry,
            trust_policy=policy,
            require_trusted=args.require_signed_registry,
        )
    except (OSError, BackendIdentityRegistryError, TrustPolicyError) as exc:
        code = getattr(exc, "error_code", type(exc).__name__)
        print(f"Backend Registry verify failed: {code}: {exc}", file=sys.stderr)
        return 1
    output = {
        "registry_id": result.registry_id,
        "registry_signed": result.registry_signed,
        "registry_signature_status": result.registry_signature_status,
        "registry_provenance_status": result.registry_provenance_status,
        "registry_authority_id": result.registry_authority_id,
        "registry_error_code": result.registry_error_code,
        "message": result.message,
    }
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(
            "Backend Registry verified: "
            f"registry_id={result.registry_id} "
            f"registry_signed={str(result.registry_signed).lower()} "
            f"registry_signature_status={result.registry_signature_status} "
            f"registry_provenance_status={result.registry_provenance_status} "
            f"authority_id={result.registry_authority_id}"
        )
    return 0 if result.ok else 1


def _inspect(args: argparse.Namespace) -> int:
    try:
        registry = load_backend_identity_registry(args.registry)
    except (OSError, BackendIdentityRegistryError) as exc:
        code = getattr(exc, "error_code", type(exc).__name__)
        print(f"Backend Registry inspect failed: {code}: {exc}", file=sys.stderr)
        return 1
    output = {
        "registry_id": registry.registry_id,
        "registry_signed": registry.signed,
        "backend_ids": [
            backend["backend_id"]
            for backend in registry.data.get("backends", [])
            if isinstance(backend, dict) and isinstance(backend.get("backend_id"), str)
        ],
    }
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(f"Backend Registry: registry_id={registry.registry_id} registry_signed={str(registry.signed).lower()}")
        for backend_id in output["backend_ids"]:
            print(f"  backend_id={backend_id}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "verify":
        return _verify(args)
    if args.command == "inspect":
        return _inspect(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

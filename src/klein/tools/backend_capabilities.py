"""CLI for Backend Capability Declaration v1 verification."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.crypto.capabilities import (
    BackendCapabilityError,
    load_backend_capability_declaration,
    verify_backend_capability_declaration,
)
from klein.crypto.registry import BackendIdentityRegistryError, load_backend_identity_registry
from klein.crypto.trust import TrustPolicyError, load_trust_policy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="klein-backend-capabilities",
        description="Inspect and verify Klein Backend Capability Declaration v1 files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify", help="Verify declaration signature/trust/scope.")
    verify.add_argument("--declaration", type=Path, required=True)
    verify.add_argument("--backend-registry", type=Path)
    verify.add_argument("--trust-policy", type=Path)
    verify.add_argument("--backend-id")
    verify.add_argument("--backend-version")
    verify.add_argument("--profile-id")
    verify.add_argument("--profile-version")
    verify.add_argument("--mode")
    verify.add_argument("--substrate-fingerprint")
    verify.add_argument("--require-trust", action="store_true")
    verify.add_argument("--json", action="store_true")

    inspect = subparsers.add_parser("inspect", help="Inspect declaration summary.")
    inspect.add_argument("--declaration", type=Path, required=True)
    inspect.add_argument("--json", action="store_true")
    return parser


def _verify(args: argparse.Namespace) -> int:
    try:
        declaration = load_backend_capability_declaration(args.declaration)
        registry = load_backend_identity_registry(args.backend_registry) if args.backend_registry else None
        policy = load_trust_policy(args.trust_policy) if args.trust_policy else None
        result = verify_backend_capability_declaration(
            declaration,
            registry=registry,
            trust_policy=policy,
            backend_id=args.backend_id,
            backend_version=args.backend_version,
            profile_id=args.profile_id,
            profile_version=args.profile_version,
            mode=args.mode,
            substrate_fingerprint=args.substrate_fingerprint,
            require_trust=args.require_trust,
        )
    except (OSError, BackendCapabilityError, BackendIdentityRegistryError, TrustPolicyError) as exc:
        code = getattr(exc, "error_code", type(exc).__name__)
        print(f"Backend Capability verify failed: {code}: {exc}", file=sys.stderr)
        return 1
    output = result.__dict__
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(
            "Backend Capability verified: "
            f"backend_id={result.backend_id} "
            f"signature_status={result.signature_status} "
            f"identity_status={result.identity_status} "
            f"trust_status={result.trust_status} "
            f"capability_scope_status={result.capability_scope_status} "
            f"declaration_hash={result.declaration_hash}"
        )
    return 0 if result.ok else 1


def _inspect(args: argparse.Namespace) -> int:
    try:
        declaration = load_backend_capability_declaration(args.declaration)
    except (OSError, BackendCapabilityError) as exc:
        code = getattr(exc, "error_code", type(exc).__name__)
        print(f"Backend Capability inspect failed: {code}: {exc}", file=sys.stderr)
        return 1
    payload = declaration["payload"]
    output = {
        "declaration_id": payload.get("declaration_id"),
        "backend_id": payload.get("backend_id"),
        "backend_version": payload.get("backend_version"),
        "supported_profiles": payload.get("supported_profiles", []),
    }
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
    else:
        print(
            "Backend Capability: "
            f"declaration_id={output['declaration_id']} "
            f"backend_id={output['backend_id']} "
            f"backend_version={output['backend_version']}"
        )
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

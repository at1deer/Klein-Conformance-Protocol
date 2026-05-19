"""CLI for Klein Run Manifest v1 creation, verification, and inspection."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from klein.crypto.keys import (
    CRYPTO_EXTRA_MESSAGE,
    load_ed25519_private_key,
    load_ed25519_public_key,
)
from klein.crypto.manifest import (
    RunManifestError,
    build_run_manifest_payload,
    load_hail_jsonl,
    load_run_manifest,
    sign_run_manifest,
    unsigned_run_manifest,
    verify_run_manifest,
)
from klein.crypto.registry import BackendIdentityRegistryError, load_backend_identity_registry
from klein.crypto.trust import TrustPolicyError, load_trust_policy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="klein-run-manifest",
        description="Create, verify, and inspect Klein Run Manifest v1 files.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create", help="Create a Run Manifest v1 from lifecycle HAIL.")
    create.add_argument("--hail", type=Path, required=True, help="Lifecycle-bound HAIL JSONL input.")
    create.add_argument("--private-key", type=Path, help="PEM Ed25519 private key for signing.")
    create.add_argument("--key-id", default="klein-test-backend-001", help="Backend identity key id.")
    create.add_argument("--output", type=Path, required=True, help="Manifest JSON output path.")
    create.add_argument("--conformance-report", type=Path, help="Optional conformance report JSON.")
    create.add_argument("--created-at", default=None, help="Fixed creation timestamp, or omit for null.")
    create.add_argument("--unsigned", action="store_true", help="Write an unsigned manifest payload.")

    verify = subparsers.add_parser("verify", help="Verify a Run Manifest v1.")
    verify.add_argument("--manifest", type=Path, required=True, help="Manifest JSON path.")
    verify.add_argument("--hail", type=Path, help="Optional HAIL JSONL stream to check payload binding.")
    verify.add_argument("--trusted-key-id", help="Require a matching signature key id.")
    verify.add_argument("--trusted-public-key", type=Path, help="Require a matching PEM public key.")
    verify.add_argument("--trust-policy", type=Path, help="Trust Policy v1 JSON for backend identity authorization.")
    verify.add_argument("--backend-registry", type=Path, help="Backend Identity Registry v1 JSON for identity resolution.")
    verify.add_argument("--require-signed-registry", action="store_true", help="Require trusted signed registry provenance.")
    verify.add_argument("--json", action="store_true", help="Emit stable JSON verification output.")

    inspect = subparsers.add_parser("inspect", help="Print stable manifest summary JSON.")
    inspect.add_argument("--manifest", type=Path, required=True, help="Manifest JSON path.")
    return parser


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _create(args: argparse.Namespace) -> int:
    try:
        events = load_hail_jsonl(args.hail)
        conformance_report = _load_json(args.conformance_report) if args.conformance_report else None
        payload = build_run_manifest_payload(
            events,
            conformance_summary=conformance_report,
            created_at=args.created_at,
        )
        if args.unsigned:
            manifest = unsigned_run_manifest(payload)
        else:
            if args.private_key is None:
                print("--private-key is required unless --unsigned is used", file=sys.stderr)
                return 1
            private_key = load_ed25519_private_key(args.private_key)
            manifest = sign_run_manifest(payload, private_key, key_id=args.key_id)
    except RuntimeError as exc:
        print(str(exc) or CRYPTO_EXTRA_MESSAGE, file=sys.stderr)
        return 1
    except (OSError, RunManifestError, ValueError) as exc:
        code = getattr(exc, "error_code", type(exc).__name__)
        print(f"Run Manifest create failed: {code}: {exc}", file=sys.stderr)
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"created {args.output}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    try:
        manifest = load_run_manifest(args.manifest)
        events = load_hail_jsonl(args.hail) if args.hail else None
        trusted_public_key = (
            load_ed25519_public_key(args.trusted_public_key) if args.trusted_public_key else None
        )
        trust_policy = load_trust_policy(args.trust_policy) if args.trust_policy else None
        backend_registry = load_backend_identity_registry(args.backend_registry) if args.backend_registry else None
        verification = verify_run_manifest(
            manifest,
            events=events,
            trusted_key_id=args.trusted_key_id,
            trusted_public_key=trusted_public_key,
            trust_policy=trust_policy,
            backend_registry=backend_registry,
            require_registry_provenance=args.require_signed_registry,
        )
    except RuntimeError as exc:
        print(str(exc) or CRYPTO_EXTRA_MESSAGE, file=sys.stderr)
        return 1
    except (OSError, RunManifestError, TrustPolicyError, BackendIdentityRegistryError, ValueError) as exc:
        code = getattr(exc, "error_code", type(exc).__name__)
        print(f"Run Manifest verify failed: {code}: {exc}", file=sys.stderr)
        return 1

    output = {
        "ok": verification.ok,
        "signature_count": verification.signature_count,
        "key_ids": list(verification.verified_key_ids),
        "signature_status": verification.signature_status,
        "trust_status": verification.trust_status,
        "trust_reason": verification.trust_reason,
        "identity_status": verification.identity_status,
        "backend_registry_id": verification.backend_registry_id,
        "registry_backend_id": verification.registry_backend_id,
        "registry_key_id": verification.registry_key_id,
        "registry_key_status": verification.registry_key_status,
        "registry_signed": verification.registry_signed,
        "registry_signature_status": verification.registry_signature_status,
        "registry_provenance_status": verification.registry_provenance_status,
        "registry_authority_id": verification.registry_authority_id,
        "key_lifecycle_status": verification.key_lifecycle_status,
        "registry_error_code": verification.error_code if verification.identity_status != "resolved" else None,
        "error_code": verification.error_code,
        "message": verification.message,
    }
    if args.json:
        print(json.dumps(output, indent=2, sort_keys=True))
        return 0 if verification.ok else 1

    if not verification.ok:
        if verification.signature_status == "valid" and verification.trust_status in {"untrusted", "indeterminate"}:
            key_ids = ",".join(verification.verified_key_ids)
            print(
                "Run Manifest signature valid but untrusted: "
                f"key_ids={key_ids} reason={verification.trust_reason}",
                file=sys.stderr,
            )
            return 1
        print(
            f"Run Manifest verify failed: {verification.error_code}: {verification.message}",
            file=sys.stderr,
        )
        return 1

    key_ids = ",".join(verification.verified_key_ids)
    print(
        "Run Manifest verified: "
        f"signatures={verification.signature_count} "
        f"key_ids={key_ids} "
        f"signature_status={verification.signature_status} "
        f"identity_status={verification.identity_status} "
        f"registry_signature_status={verification.registry_signature_status} "
        f"registry_provenance_status={verification.registry_provenance_status} "
        f"trust_status={verification.trust_status}"
    )
    return 0


def _inspect(args: argparse.Namespace) -> int:
    try:
        manifest = load_run_manifest(args.manifest)
        payload = manifest.get("payload", {})
        signatures = manifest.get("signatures", [])
    except (OSError, RunManifestError) as exc:
        code = getattr(exc, "error_code", type(exc).__name__)
        print(f"Run Manifest inspect failed: {code}: {exc}", file=sys.stderr)
        return 1

    summary = {
        "manifest_version": manifest.get("manifest_version"),
        "run_id": payload.get("run_id") if isinstance(payload, dict) else None,
        "hail_digest": payload.get("hail_digest") if isinstance(payload, dict) else None,
        "hail_chain_digest": payload.get("hail_chain_digest") if isinstance(payload, dict) else None,
        "backend_id": payload.get("backend_id") if isinstance(payload, dict) else None,
        "run_status": payload.get("run_status") if isinstance(payload, dict) else None,
        "signature_count": len(signatures) if isinstance(signatures, list) else None,
        "key_ids": [
            signature.get("key_id")
            for signature in signatures
            if isinstance(signature, dict) and isinstance(signature.get("key_id"), str)
        ]
        if isinstance(signatures, list)
        else [],
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "create":
        return _create(args)
    if args.command == "verify":
        return _verify(args)
    if args.command == "inspect":
        return _inspect(args)
    return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

"""CLI for Attestation Profile v1 stub artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from klein.attestation.profile import (
    ATTESTATION_PROFILE_VERSION,
    canonical_attestation_profile_hash,
    validate_attestation_profile,
)
from klein.attestation.statement import (
    ATTESTATION_STATEMENT_VERSION,
    canonical_attestation_statement_hash,
    inspect_attestation_statement,
    validate_attestation_statement,
    verify_attestation_statement_binding,
)
from klein.common.hashing import canonical_json_bytes, parse_ijson


def _load_json(path: Path) -> dict:
    data = parse_ijson(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("attestation artifact root must be an object")
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(data) + b"\n")


def _print_validation(ok: bool, error_code: str | None, message: str | None) -> int:
    if ok:
        print("valid mock/null attestation artifact; hardware_attestation_claimed=false; no hardware attestation proof")
        return 0
    print(f"invalid attestation artifact: {error_code}: {message}", file=sys.stderr)
    return 1


def _validate_profile(args: argparse.Namespace) -> int:
    result = validate_attestation_profile(_load_json(args.path))
    return _print_validation(result.ok, result.error_code, result.message)


def _validate_statement(args: argparse.Namespace) -> int:
    result = validate_attestation_statement(_load_json(args.path))
    return _print_validation(result.ok, result.error_code, result.message)


def _hash_profile(args: argparse.Namespace) -> int:
    print(canonical_attestation_profile_hash(args.path).ref)
    return 0


def _hash_statement(args: argparse.Namespace) -> int:
    print(canonical_attestation_statement_hash(args.path).ref)
    return 0


def _verify_binding(args: argparse.Namespace) -> int:
    result = verify_attestation_statement_binding(
        _load_json(args.statement),
        subject_hash=args.subject_hash,
        backend_id=args.backend_id,
    )
    return _print_validation(result.ok, result.error_code, result.message)


def _inspect_statement(args: argparse.Namespace) -> int:
    inspection = inspect_attestation_statement(_load_json(args.path))
    print(
        json.dumps(
            {
                "attestation_status": inspection.attestation_status,
                "hardware_attestation_claimed": inspection.hardware_attestation_claimed,
                "statement_kind": inspection.statement_kind,
                "subject_type": inspection.subject_type,
                "subject_id": inspection.subject_id,
                "subject_hash": inspection.subject_hash,
                "backend_id": inspection.backend_id,
                "message": inspection.message,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if inspection.attestation_status in {"none", "mock"} else 1


def _statement(args: argparse.Namespace, statement_kind: str) -> dict:
    backend_id = args.backend_id
    return {
        "attestation_statement_version": ATTESTATION_STATEMENT_VERSION,
        "statement_id": args.statement_id,
        "statement_kind": statement_kind,
        "subject": {
            "subject_type": args.subject_type,
            "subject_id": args.subject_id or backend_id,
            "subject_hash": args.subject_hash,
        },
        "backend": {
            "backend_id": backend_id,
            "backend_version": args.backend_version,
        },
        "hardware_attestation_claimed": False,
        "hardware_root": None,
        "quote": None,
        "measurements": [],
        "signature": None,
        "metadata": {},
    }


def _create_statement(args: argparse.Namespace, statement_kind: str) -> int:
    data = _statement(args, statement_kind)
    result = validate_attestation_statement(data)
    if not result.ok:
        return _print_validation(False, result.error_code, result.message)
    _write_json(args.output, data)
    print(
        "created mock/null attestation statement; hardware_attestation_claimed=false; "
        "no hardware attestation proof"
    )
    return 0


def _create_mock(args: argparse.Namespace) -> int:
    return _create_statement(args, "mock")


def _create_none(args: argparse.Namespace) -> int:
    return _create_statement(args, "none")


def _create_profile(args: argparse.Namespace) -> int:
    data = {
        "attestation_profile_version": ATTESTATION_PROFILE_VERSION,
        "profile_id": args.profile_id,
        "profile_kind": "mock_none",
        "hardware_attestation_claimed": False,
        "allowed_statement_kinds": ["none", "mock"],
        "requires_hardware_root": False,
        "trust_roots": [],
        "limitations": [
            "Mock/null attestation profile only.",
            "No hardware attestation proof is claimed.",
        ],
    }
    _write_json(args.output, data)
    print("created mock/null attestation profile; no hardware attestation proof")
    return 0


def _add_create_statement_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--subject-type", required=True, choices=["backend", "run_bundle", "recorded_run", "device"])
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--statement-id", default="mock-attestation-001")
    parser.add_argument("--subject-id", default=None)
    parser.add_argument("--subject-hash", default=None)
    parser.add_argument("--backend-id", default=None)
    parser.add_argument("--backend-version", default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate mock/null Klein attestation stub artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_profile = sub.add_parser("validate-profile")
    validate_profile.add_argument("path", type=Path)
    validate_profile.set_defaults(func=_validate_profile)

    validate_statement = sub.add_parser("validate-statement")
    validate_statement.add_argument("path", type=Path)
    validate_statement.set_defaults(func=_validate_statement)

    hash_profile = sub.add_parser("hash-profile")
    hash_profile.add_argument("path", type=Path)
    hash_profile.set_defaults(func=_hash_profile)

    hash_statement = sub.add_parser("hash-statement")
    hash_statement.add_argument("path", type=Path)
    hash_statement.set_defaults(func=_hash_statement)

    verify_binding = sub.add_parser("verify-binding")
    verify_binding.add_argument("--statement", required=True, type=Path)
    verify_binding.add_argument("--subject-hash", default=None)
    verify_binding.add_argument("--backend-id", default=None)
    verify_binding.set_defaults(func=_verify_binding)

    inspect_statement = sub.add_parser("inspect-statement")
    inspect_statement.add_argument("path", type=Path)
    inspect_statement.set_defaults(func=_inspect_statement)

    create_mock = sub.add_parser("create-mock")
    _add_create_statement_args(create_mock)
    create_mock.set_defaults(func=_create_mock)

    create_none = sub.add_parser("create-none")
    _add_create_statement_args(create_none)
    create_none.set_defaults(func=_create_none)

    create_profile = sub.add_parser("create-profile")
    create_profile.add_argument("--output", required=True, type=Path)
    create_profile.add_argument("--profile-id", default="mock-attestation-alpha")
    create_profile.set_defaults(func=_create_profile)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"klein-attestation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

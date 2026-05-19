"""CLI for Trusted Timestamp Profile v1 stub artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from klein.common.hashing import canonical_json_bytes, parse_ijson
from klein.timestamping.profile import (
    TIMESTAMP_PROFILE_VERSION,
    canonical_timestamp_profile_hash,
    validate_timestamp_profile,
)
from klein.timestamping.token import (
    TIMESTAMP_TOKEN_VERSION,
    canonical_timestamp_token_hash,
    inspect_timestamp_token,
    validate_timestamp_token,
    verify_timestamp_token_binding,
)


def _load_json(path: Path) -> dict:
    data = parse_ijson(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("timestamp artifact root must be an object")
    return data


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(data) + b"\n")


def _print_validation(ok: bool, error_code: str | None, message: str | None) -> int:
    if ok:
        print("valid mock/local timestamp artifact; trusted_time_claimed=false; no trusted timestamp proof")
        return 0
    print(f"invalid timestamp artifact: {error_code}: {message}", file=sys.stderr)
    return 1


def _validate_profile(args: argparse.Namespace) -> int:
    result = validate_timestamp_profile(_load_json(args.path))
    return _print_validation(result.ok, result.error_code, result.message)


def _validate_token(args: argparse.Namespace) -> int:
    result = validate_timestamp_token(_load_json(args.path))
    return _print_validation(result.ok, result.error_code, result.message)


def _hash_profile(args: argparse.Namespace) -> int:
    print(canonical_timestamp_profile_hash(args.path).ref)
    return 0


def _hash_token(args: argparse.Namespace) -> int:
    print(canonical_timestamp_token_hash(args.path).ref)
    return 0


def _verify_binding(args: argparse.Namespace) -> int:
    result = verify_timestamp_token_binding(_load_json(args.token), args.target_hash)
    return _print_validation(result.ok, result.error_code, result.message)


def _inspect_token(args: argparse.Namespace) -> int:
    inspection = inspect_timestamp_token(_load_json(args.path))
    print(
        json.dumps(
            {
                "timestamp_status": inspection.timestamp_status,
                "trusted_time_claimed": inspection.trusted_time_claimed,
                "token_kind": inspection.token_kind,
                "target_type": inspection.target_type,
                "target_hash": inspection.target_hash,
                "message": inspection.message,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if inspection.timestamp_status == "mock" else 1


def _create_mock(args: argparse.Namespace) -> int:
    data = {
        "timestamp_token_version": TIMESTAMP_TOKEN_VERSION,
        "token_id": args.token_id,
        "token_kind": "mock_local",
        "target": {
            "target_type": args.target_type,
            "target_hash": args.target_hash,
            "target_canonicalization": args.target_canonicalization,
        },
        "claimed_time": args.claimed_time,
        "time_source": {
            "source_type": args.source_type,
            "authority_id": None,
        },
        "trusted_time_claimed": False,
        "signature": None,
        "metadata": {},
    }
    result = validate_timestamp_token(data)
    if not result.ok:
        return _print_validation(False, result.error_code, result.message)
    _write_json(args.output, data)
    print(
        "created mock/local timestamp token; trusted_time_claimed=false; "
        "no trusted timestamp proof"
    )
    return 0


def _create_profile(args: argparse.Namespace) -> int:
    data = {
        "timestamp_profile_version": TIMESTAMP_PROFILE_VERSION,
        "profile_id": args.profile_id,
        "profile_kind": "mock_local",
        "trusted_time_claimed": False,
        "allowed_token_kinds": ["mock_local"],
        "requires_external_time_authority": False,
        "trust_roots": [],
        "limitations": [
            "Mock/local timestamp profile only.",
            "No trusted timestamp proof is claimed.",
        ],
    }
    _write_json(args.output, data)
    print("created mock/local timestamp profile; no trusted timestamp proof")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate mock/local Klein timestamp stub artifacts.")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_profile = sub.add_parser("validate-profile")
    validate_profile.add_argument("path", type=Path)
    validate_profile.set_defaults(func=_validate_profile)

    validate_token = sub.add_parser("validate-token")
    validate_token.add_argument("path", type=Path)
    validate_token.set_defaults(func=_validate_token)

    hash_profile = sub.add_parser("hash-profile")
    hash_profile.add_argument("path", type=Path)
    hash_profile.set_defaults(func=_hash_profile)

    hash_token = sub.add_parser("hash-token")
    hash_token.add_argument("path", type=Path)
    hash_token.set_defaults(func=_hash_token)

    verify_binding = sub.add_parser("verify-binding")
    verify_binding.add_argument("--token", required=True, type=Path)
    verify_binding.add_argument("--target-hash", required=True)
    verify_binding.set_defaults(func=_verify_binding)

    inspect_token = sub.add_parser("inspect-token")
    inspect_token.add_argument("path", type=Path)
    inspect_token.set_defaults(func=_inspect_token)

    create_mock = sub.add_parser("create-mock")
    create_mock.add_argument("--target-type", required=True)
    create_mock.add_argument("--target-hash", required=True)
    create_mock.add_argument("--output", required=True, type=Path)
    create_mock.add_argument("--token-id", default="mock-token-001")
    create_mock.add_argument("--claimed-time", default="2026-05-18T00:00:00Z")
    create_mock.add_argument("--source-type", choices=["local_clock", "mock"], default="local_clock")
    create_mock.add_argument("--target-canonicalization", default="klein.canon.json.v1")
    create_mock.set_defaults(func=_create_mock)

    create_profile = sub.add_parser("create-profile")
    create_profile.add_argument("--output", required=True, type=Path)
    create_profile.add_argument("--profile-id", default="mock-local-alpha")
    create_profile.set_defaults(func=_create_profile)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:
        print(f"klein-timestamp failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

#!/usr/bin/env python3
"""Canonicalize and verify HAIL v1 JSONL streams."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from klein.hail.canonical import canonicalize_hail_jsonl, digest_hail_jsonl
from klein.hail.chain import chain_digest_hail_jsonl, verify_hail_chain
from klein.hail.validation import parse_jsonl_events


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="klein-hail-canon",
        description="Validate HAIL v1 JSONL and emit Klein/JCS canonical JSONL bytes.",
    )
    parser.add_argument("input", type=Path, help="Input HAIL JSONL file.")
    parser.add_argument("--output", type=Path, help="Write canonical JSONL bytes to this path.")
    parser.add_argument("--digest", action="store_true", help="Print SHA-256 digest of canonical bytes.")
    parser.add_argument(
        "--chain-digest",
        action="store_true",
        help="Print the Klein HAIL chain v1 terminal digest.",
    )
    parser.add_argument(
        "--verify-chain",
        action="store_true",
        help="Verify RUN_END.preclose_hail_chain_digest and canonical event order.",
    )
    parser.add_argument("--check", type=Path, help="Compare canonical bytes with an expected JSONL file.")
    parser.add_argument("--check-digest", help="Compare canonical SHA-256 digest with this hex value.")
    return parser.parse_args(argv)


def _read_expected_bytes(path: Path) -> bytes:
    payload = path.read_bytes()
    if payload.endswith(b"\r\n"):
        raise ValueError("expected canonical JSONL must use LF line endings, not CRLF")
    if payload.endswith(b"\n"):
        return payload[:-1]
    return payload


def _normalize_digest(value: str) -> str:
    lowered = value.strip().lower()
    if lowered.startswith("sha256:"):
        lowered = lowered.removeprefix("sha256:")
    return lowered


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    try:
        payload = args.input.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"failed to read {args.input}: {exc}", file=sys.stderr)
        return 1

    validation, events = parse_jsonl_events(payload)
    if not validation.ok:
        location = f" line={validation.index}" if validation.index is not None else ""
        print(
            f"HAIL validation failed: {validation.error_code} "
            f"stage={validation.validation_stage}{location}: {validation.message}",
            file=sys.stderr,
        )
        return 1

    try:
        canonical = canonicalize_hail_jsonl(events)
    except (TypeError, ValueError) as exc:
        print(f"HAIL canonicalization failed: {exc}", file=sys.stderr)
        return 1

    digest = digest_hail_jsonl(events)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical)
    elif (
        not args.check
        and not args.digest
        and not args.check_digest
        and not args.chain_digest
        and not args.verify_chain
    ):
        sys.stdout.buffer.write(canonical)

    if args.check:
        try:
            expected = _read_expected_bytes(args.check)
        except (OSError, ValueError) as exc:
            print(f"failed to read expected canonical JSONL: {exc}", file=sys.stderr)
            return 1
        if expected != canonical:
            print("canonical JSONL mismatch", file=sys.stderr)
            return 1

    if args.check_digest:
        expected_digest = _normalize_digest(args.check_digest)
        if expected_digest != digest:
            print(f"digest mismatch: expected {expected_digest}, actual {digest}", file=sys.stderr)
            return 1

    if args.verify_chain:
        verification = verify_hail_chain(events)
        if not verification.ok:
            print(
                f"HAIL chain verification failed: {verification.error_code}: "
                f"{verification.reason}",
                file=sys.stderr,
            )
            return 1

    if args.chain_digest:
        try:
            print(chain_digest_hail_jsonl(events))
        except (TypeError, ValueError) as exc:
            print(f"HAIL chain digest failed: {exc}", file=sys.stderr)
            return 1

    if args.digest:
        print(f"sha256:{digest}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""CLI for canonical Klein artifact hashes."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from klein.common.hashing import hash_json_artifact, raw_file_sha256
from klein.hail.canonical import digest_hail_jsonl
from klein.hail.validation import parse_jsonl_events


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Hash a Klein artifact using canonical bytes.")
    parser.add_argument("path", type=Path, help=".klein, .kleinc, JSON, or HAIL JSONL file")
    parser.add_argument(
        "--type",
        choices=["json", "hail_jsonl", "raw"],
        default=None,
        help="Artifact interpretation. Defaults to hail_jsonl for .jsonl, otherwise json.",
    )
    parser.add_argument("--bare", action="store_true", help="Print bare hex digest instead of sha256:<hex>.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    path: Path = args.path
    artifact_type = args.type or ("hail_jsonl" if path.suffix == ".jsonl" else "json")

    try:
        if artifact_type == "raw":
            result = raw_file_sha256(path)
        elif artifact_type == "hail_jsonl":
            validation, events = parse_jsonl_events(path.read_text(encoding="utf-8"))
            if not validation.ok:
                print(
                    f"HAIL validation failed at {validation.validation_stage}: {validation.message}",
                    file=sys.stderr,
                )
                return 1
            digest = digest_hail_jsonl(events)
            print(digest if args.bare else f"sha256:{digest}")
            return 0
        else:
            result = hash_json_artifact(path)
    except Exception as exc:
        print(f"artifact hash failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print(result.digest_hex if args.bare else result.ref)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

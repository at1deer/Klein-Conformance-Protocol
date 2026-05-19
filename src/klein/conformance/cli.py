"""Command line interface for klein-conform."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from klein.conformance.backends import create_backend
from klein.conformance.models import (
    BackendType,
    CompareMode,
    ConformanceReport,
    ConformanceResult,
    Outcome,
    VectorLoadError,
)
from klein.conformance.runner import run_vector
from klein.conformance.suite import (
    DEFAULT_LEGACY_SUITE_DIR,
    check_v1_suite_integrity,
    discover_vectors,
    resolve_suite_dir,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="klein-conform",
        description="Klein Conformance Test Harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Backend Types:
  mock            Returns golden observables (for harness testing)
  subprocess      Calls klein-sim via subprocess (default)
  simulator       Uses Python API directly (faster, A* only)
  full_simulator  Full execution engine with payload/container support
  substrate       Direct hardware driver (future)

Examples:
  klein-conform --list
  klein-conform --list-vectors
  klein-conform --suite tests/vectors/v1 --smoke
  klein-conform --vector 001 --vector N003
  klein-conform --backend simulator --category positive
  klein-conform --json > results.json
        """,
    )

    parser.add_argument(
        "--vector",
        "-v",
        action="append",
        dest="vectors",
        metavar="ID",
        help="Run specific vector(s) by ID (e.g., -v 001 -v N003)",
    )

    parser.add_argument(
        "--category",
        "-c",
        choices=["positive", "negative", "all"],
        default="all",
        help="Filter by test category (default: all)",
    )

    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run only smoke tests (small representative subset)",
    )

    parser.add_argument(
        "--suite",
        type=Path,
        default=None,
        help="Vector suite directory (default: tests/vectors/v1 when present)",
    )

    parser.add_argument(
        "--legacy",
        action="store_true",
        help="Run the legacy exp_v0.1 vector namespace instead of v1",
    )

    parser.add_argument(
        "--backend",
        "-b",
        choices=["mock", "subprocess", "simulator", "full_simulator", "substrate"],
        default="subprocess",
        help="Backend to use for execution (default: subprocess). Use full_simulator for complete container execution.",
    )

    parser.add_argument(
        "--compare-mode",
        "-m",
        choices=["EXACT_JSONL", "SET", "ENVELOPE"],
        default="EXACT_JSONL",
        help="Comparison mode (default: EXACT_JSONL)",
    )

    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Timeout per vector in seconds (default: 30)",
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON",
    )

    parser.add_argument(
        "--failures-only",
        action="store_true",
        help="Only print failing/error results in human output; filters JSON results when used with --json.",
    )

    parser.add_argument(
        "--limit-failures",
        type=int,
        default=10,
        help="Maximum number of failure details to print in human output (default: 10).",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        dest="list_only",
        help="List available vectors without running",
    )

    parser.add_argument(
        "--list-vectors",
        action="store_true",
        dest="list_only",
        help="Alias for --list.",
    )

    parser.add_argument(
        "--check-suite-integrity",
        action="store_true",
        help="Validate v1 suite structure and exit without running vectors.",
    )

    return parser.parse_args(argv)


def print_result(result: ConformanceResult, verbose: bool = False) -> None:
    """Print a single test result."""
    # Use ASCII-safe icons for Windows compatibility
    icon = {
        Outcome.PASS: "[PASS]",
        Outcome.FAIL: "[FAIL]",
        Outcome.SKIP: "[SKIP]",
        Outcome.ERROR: "[ERR!]",
    }[result.outcome]

    color = {
        Outcome.PASS: "\033[92m",  # Green
        Outcome.FAIL: "\033[91m",  # Red
        Outcome.SKIP: "\033[93m",  # Yellow
        Outcome.ERROR: "\033[95m",  # Magenta
    }[result.outcome]

    reset = "\033[0m"

    print(f"  {color}{icon}{reset} [{result.vector_id}] {result.message}", end="")
    if verbose and result.duration_ms > 0:
        print(f" ({result.duration_ms:.1f}ms)", end="")
    print()


def print_failure_details(results: list[ConformanceResult], *, limit: int) -> None:
    """Print compact failure details for human CLI output."""
    failures = [r for r in results if r.outcome in {Outcome.FAIL, Outcome.ERROR}]
    if not failures:
        return
    shown = failures[: max(limit, 0)]
    print()
    print(f"First {len(shown)} failure(s):")
    for result in shown:
        print(
            f"  [{result.vector_id}] outcome={result.outcome.value} "
            f"expected={result.expected_result}/{result.expected_error_code} "
            f"actual={result.actual_result}/{result.actual_error_code} "
            f"stage={result.validation_stage or '-'}"
        )
        print(f"    reason={result.reason or result.message}")
    remaining = len(failures) - len(shown)
    if remaining > 0:
        print(f"  ... {remaining} more failure(s) omitted; use --limit-failures to adjust.")


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    args = parse_args(argv)

    # Smoke test vector IDs (representative subset)
    suite_dir = resolve_suite_dir(args.suite, legacy=args.legacy)
    smoke_vectors = ["001", "002", "003", "004", "005"]
    if args.legacy or suite_dir == DEFAULT_LEGACY_SUITE_DIR:
        smoke_vectors = ["001", "002", "004", "005", "021", "022", "113"]

    # Discover vectors
    try:
        if args.check_suite_integrity:
            issues = [] if args.legacy else check_v1_suite_integrity(suite_dir)
            if args.json:
                print(
                    json.dumps(
                        {
                            "summary": {
                                "backend": args.backend,
                                "total": 0,
                                "passed": 0 if issues else 1,
                                "failed": 1 if issues else 0,
                                "skipped": 0,
                                "errors": 0,
                                "success_rate": 0.0 if issues else 100.0,
                                "legacy_namespace": args.legacy,
                                "authoritative_v1": not args.legacy,
                            },
                            "integrity_issues": issues,
                        },
                        indent=2,
                    )
                )
            elif issues:
                print(f"Suite integrity failed: {len(issues)} issue(s)", file=sys.stderr)
                for issue in issues[: args.limit_failures]:
                    print(f"  {issue['code']}: {issue['message']}", file=sys.stderr)
            else:
                print(f"Suite integrity ok: {suite_dir}")
            return 1 if issues else 0

        if args.smoke:
            vectors = discover_vectors(
                vector_ids=smoke_vectors,
                suite_dir=suite_dir,
                legacy=args.legacy,
            )
        else:
            vectors = discover_vectors(
                vector_ids=args.vectors,
                category=args.category if args.category != "all" else None,
                suite_dir=suite_dir,
                legacy=args.legacy,
            )
    except VectorLoadError as exc:
        if args.json:
            print(
                json.dumps(
                    {
                        "summary": {
                            "backend": args.backend,
                            "total": 0,
                            "passed": 0,
                            "failed": 0,
                            "skipped": 0,
                            "errors": 1,
                            "success_rate": 0.0,
                            "legacy_namespace": args.legacy,
                            "authoritative_v1": not args.legacy,
                        },
                        "errors": [
                            {
                                "error_code": exc.error_code,
                                "validation_stage": exc.validation_stage,
                                "message": str(exc),
                                "detail": exc.detail,
                            }
                        ],
                    },
                    indent=2,
                )
            )
        else:
            print(f"{exc.error_code}: {exc}", file=sys.stderr)
        return 1

    if not vectors:
        print("No test vectors found.", file=sys.stderr)
        return 1

    # List only?
    if args.list_only:
        print(f"Available vectors ({len(vectors)}):\n")
        for v in vectors:
            neg_marker = " [NEGATIVE]" if v.is_negative else ""
            src = v.input_type or ("klnc" if v.container else ("loose" if v.loose_path else "none"))
            print(f"  [{v.id}] ({src}) {v.purpose}{neg_marker}")
        return 0

    # Create backend
    backend_type = BackendType(args.backend)
    backend = create_backend(
        backend_type,
        timeout_seconds=args.timeout,
    )

    # Run tests
    if not args.json:
        authoritative_v1 = (
            all(v.schema_version == "v1" for v in vectors)
            and backend.name == "full_simulator"
            and not args.legacy
        )
        legacy_namespace = args.legacy or not authoritative_v1
        print("\nKlein Conformance Test Suite")
        print("=" * 50)
        print(f"Backend: {backend.name}")
        print(f"Vectors: {len(vectors)}")
        print(f"Suite: {suite_dir}")
        print(f"Compare Mode: {args.compare_mode}")
        print(f"authoritative_v1: {str(authoritative_v1).lower()}")
        print(f"legacy_namespace: {str(legacy_namespace).lower()}")
        print("=" * 50)
        print()

    report = ConformanceReport()
    compare_mode = CompareMode(args.compare_mode)

    try:
        for vector in vectors:
            result = run_vector(vector, backend, compare_mode)
            report.add(result)

            if not args.json and not args.failures_only:
                print_result(result, args.verbose)
    finally:
        backend.cleanup()

    # Output
    if args.json:
        authoritative_v1 = (
            all(v.schema_version == "v1" for v in vectors)
            and backend.name == "full_simulator"
            and not args.legacy
        )
        output_results = report.results
        if args.failures_only:
            output_results = [
                r for r in output_results if r.outcome in {Outcome.FAIL, Outcome.ERROR}
            ]
        output = {
            "summary": {
                "backend": backend.name,
                "total": report.total,
                "passed": report.passed,
                "failed": report.failed,
                "skipped": report.skipped,
                "errors": report.errors,
                "success_rate": report.success_rate,
                "legacy_namespace": args.legacy or not authoritative_v1,
                "authoritative_v1": authoritative_v1,
            },
            "results": [
                {
                    "vector_id": r.vector_id,
                    "vector_name": r.vector_name,
                    "outcome": r.outcome.value,
                    "message": r.message,
                    "expected_result": r.expected_result,
                    "actual_result": r.actual_result,
                    "expected_error_code": r.expected_error_code,
                    "actual_error_code": r.actual_error_code,
                    "validation_stage": r.validation_stage,
                    "reason": r.reason,
                    "duration_ms": r.duration_ms,
                    "expected_error": r.expected_error,
                    "actual_error": r.actual_error,
                    "classification": r.details.get("classification"),
                    "details": r.details,
                }
                for r in output_results
            ],
        }
        print(json.dumps(output, indent=2))
    else:
        if args.failures_only:
            for result in report.results:
                if result.outcome in {Outcome.FAIL, Outcome.ERROR}:
                    print_result(result, args.verbose)
        print()
        print("=" * 50)
        print(report.summary())
        authoritative_v1 = (
            all(v.schema_version == "v1" for v in vectors)
            and backend.name == "full_simulator"
            and not args.legacy
        )
        legacy_namespace = args.legacy or not authoritative_v1
        print(f"authoritative_v1: {str(authoritative_v1).lower()}")
        print(f"legacy_namespace: {str(legacy_namespace).lower()}")
        print_failure_details(report.results, limit=args.limit_failures)
        print("=" * 50)

    # Exit code: 0 if all pass, 1 if any fail
    return 0 if report.failed == 0 and report.errors == 0 else 1

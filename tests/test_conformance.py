#!/usr/bin/env python3
"""
Pytest-integrated Klein Conformance Tests

This module provides pytest integration for the Klein conformance suite.

Usage:
    # Run smoke tests (default - small representative subset)
    pytest tests/test_conformance.py
    
    # Run full conformance suite
    pytest tests/test_conformance.py --full-conformance
    
    # Run specific categories
    pytest tests/test_conformance.py -k "positive"
    pytest tests/test_conformance.py -k "negative"
    
    # Run with verbose conformance output
    pytest tests/test_conformance.py -v --conformance-verbose

CLI Alternative:
    klein-conform              # Full suite
    klein-conform --smoke      # Smoke tests only
    klein-conform --help       # All options
"""

from __future__ import annotations

from typing import Any, Generator

import pytest

from klein.conformance.harness import (
    BackendType,
    CompareMode,
    ConformanceResult,
    ConformanceVector,
    Outcome,
    create_backend,
    discover_vectors,
    run_vector,
)


# =============================================================================
# Representative Smoke Test Subset
# =============================================================================

# These vectors provide broad coverage with minimal runtime:
# - .klein project execution
# - .kleinc container execution
# - HAIL JSONL validation
# - Minimal envelope comparison
# - DMF frame payload evidence
SMOKE_TEST_VECTORS = [
    "001",  # Minimal .klein project execution
    "002",  # Minimal .kleinc container execution
    "003",  # ENVELOPE tolerance comparison
    "004",  # HAIL runtime snapshot v1
    "005",  # DMF/EWOD frame payload
]


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="session")
def conformance_backend(request: pytest.FixtureRequest) -> Generator[Any, None, None]:
    """Create and yield a conformance backend for the test session."""
    backend_name = request.config.getoption("--conformance-backend")
    backend = create_backend(BackendType(backend_name), timeout_seconds=30)
    yield backend
    backend.cleanup()


@pytest.fixture(scope="session")
def all_vectors() -> list[ConformanceVector]:
    """Discover all available test vectors."""
    return discover_vectors()


@pytest.fixture(scope="session")
def smoke_vectors(all_vectors: list[ConformanceVector]) -> list[ConformanceVector]:
    """Filter vectors to smoke test subset."""
    return [v for v in all_vectors if v.id in SMOKE_TEST_VECTORS]


# =============================================================================
# Test Functions
# =============================================================================

def _run_conformance_test(
    vector: ConformanceVector,
    backend: Any,
    compare_mode: CompareMode = CompareMode.ENVELOPE,
) -> ConformanceResult:
    """Run a single conformance test and return the result."""
    return run_vector(vector, backend, compare_mode)


class TestConformanceSmokeTests:
    """
    Smoke tests - a small representative subset of the conformance suite.
    
    These run by default and provide quick feedback on basic functionality.
    Use --full-conformance to run the complete suite instead.
    """
    
    @pytest.mark.smoke
    @pytest.mark.conformance
    @pytest.mark.parametrize("vector_id", SMOKE_TEST_VECTORS)
    def test_smoke_vector(
        self,
        vector_id: str,
        conformance_backend: Any,
        all_vectors: list[ConformanceVector],
        request: pytest.FixtureRequest,
    ) -> None:
        """Run a smoke test vector."""
        # Skip if full conformance is requested (those tests are separate)
        if request.config.getoption("--full-conformance"):
            pytest.skip("Running full conformance instead of smoke tests")
        
        # Find vector
        vector = next((v for v in all_vectors if v.id == vector_id), None)
        if vector is None:
            pytest.skip(f"Vector {vector_id} not found")
        
        result = _run_conformance_test(vector, conformance_backend)
        
        # Report details on failure
        if result.outcome == Outcome.FAIL:
            pytest.fail(
                f"Conformance FAIL: {result.message}\n"
                f"Expected: {result.expected_error}\n"
                f"Actual: {result.actual_error}"
            )
        elif result.outcome == Outcome.ERROR:
            pytest.fail(f"Conformance ERROR: {result.message}")
        elif result.outcome == Outcome.SKIP:
            pytest.skip(result.message)


class TestConformanceFullSuite:
    """
    Full conformance suite - runs all test vectors.
    
    Use --full-conformance to enable these tests.
    """
    
    @pytest.mark.conformance
    def test_full_positive_vectors(
        self,
        conformance_backend: Any,
        all_vectors: list[ConformanceVector],
        request: pytest.FixtureRequest,
    ) -> None:
        """Run all positive conformance vectors."""
        if not request.config.getoption("--full-conformance"):
            pytest.skip("Use --full-conformance to run full suite")
        
        positive_vectors = [v for v in all_vectors if not v.is_negative]
        results: list[ConformanceResult] = []
        failures: list[str] = []
        
        for vector in positive_vectors:
            result = _run_conformance_test(vector, conformance_backend)
            results.append(result)
            
            if result.outcome == Outcome.FAIL:
                failures.append(f"[{vector.id}] {result.message}")
            elif result.outcome == Outcome.ERROR:
                failures.append(f"[{vector.id}] ERROR: {result.message}")
        
        passed = sum(1 for r in results if r.outcome == Outcome.PASS)
        total = len(results)
        
        if failures:
            pytest.fail(
                f"Positive vectors: {passed}/{total} passed\n"
                f"Failures:\n" + "\n".join(f"  - {f}" for f in failures[:10])
                + (f"\n  ... and {len(failures) - 10} more" if len(failures) > 10 else "")
            )
    
    @pytest.mark.conformance
    @pytest.mark.negative
    def test_full_negative_vectors(
        self,
        conformance_backend: Any,
        all_vectors: list[ConformanceVector],
        request: pytest.FixtureRequest,
    ) -> None:
        """Run all negative conformance vectors."""
        if not request.config.getoption("--full-conformance"):
            pytest.skip("Use --full-conformance to run full suite")
        
        negative_vectors = [v for v in all_vectors if v.is_negative]
        results: list[ConformanceResult] = []
        failures: list[str] = []
        
        for vector in negative_vectors:
            result = _run_conformance_test(vector, conformance_backend)
            results.append(result)
            
            if result.outcome == Outcome.FAIL:
                failures.append(f"[{vector.id}] {result.message}")
            elif result.outcome == Outcome.ERROR:
                failures.append(f"[{vector.id}] ERROR: {result.message}")
        
        passed = sum(1 for r in results if r.outcome == Outcome.PASS)
        total = len(results)
        
        if failures:
            pytest.fail(
                f"Negative vectors: {passed}/{total} passed\n"
                f"Failures:\n" + "\n".join(f"  - {f}" for f in failures[:10])
                + (f"\n  ... and {len(failures) - 10} more" if len(failures) > 10 else "")
            )


# =============================================================================
# Standalone Conformance Summary
# =============================================================================

@pytest.mark.conformance
def test_conformance_summary(
    conformance_backend: Any,
    all_vectors: list[ConformanceVector],
    request: pytest.FixtureRequest,
) -> None:
    """
    Summary test that runs all vectors and reports aggregate results.
    
    This test always passes but prints a summary. Use for CI reporting.
    """
    if not request.config.getoption("--full-conformance"):
        pytest.skip("Use --full-conformance to run full suite summary")
    
    passed = 0
    failed = 0
    skipped = 0
    errors = 0
    
    for vector in all_vectors:
        result = _run_conformance_test(vector, conformance_backend)
        if result.outcome == Outcome.PASS:
            passed += 1
        elif result.outcome == Outcome.FAIL:
            failed += 1
        elif result.outcome == Outcome.SKIP:
            skipped += 1
        else:
            errors += 1
    
    total = len(all_vectors)
    success_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\n{'=' * 50}")
    print(f"KLEIN CONFORMANCE SUMMARY")
    print(f"{'=' * 50}")
    print(f"Total:   {total}")
    print(f"Passed:  {passed}")
    print(f"Failed:  {failed}")
    print(f"Skipped: {skipped}")
    print(f"Errors:  {errors}")
    print(f"Rate:    {success_rate:.1f}%")
    print(f"{'=' * 50}")
    
    # This test reports but doesn't fail - use individual tests for failure detection

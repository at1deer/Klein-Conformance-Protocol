"""Shared conformance data models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from klein.common.models import Container


class Outcome(str, Enum):
    """Test outcome classification."""

    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"
    ERROR = "ERROR"


class CompareMode(str, Enum):
    """HAIL log comparison modes."""

    EXACT_JSONL = "EXACT_JSONL"
    SET = "SET"
    ENVELOPE = "ENVELOPE"


class BackendType(str, Enum):
    """Available backend implementations."""

    MOCK = "mock"
    SUBPROCESS = "subprocess"
    SIMULATOR = "simulator"
    FULL_SIMULATOR = "full_simulator"  # Full execution engine
    SUBSTRATE = "substrate"  # Future expansion


class VectorLoadError(ValueError):
    """Structured error for invalid vector suite metadata."""

    def __init__(
        self,
        error_code: str,
        message: str,
        *,
        validation_stage: str = "vector_metadata",
        detail: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.error_code = error_code
        self.validation_stage = validation_stage
        self.detail = detail or {}


@dataclass
class ExecutionResult:
    """Result from backend execution."""

    success: bool
    events: list[dict[str, Any]]
    error_code: str | None = None
    error_message: str | None = None
    validation_stage: str | None = None
    exit_code: int = 0
    duration_ms: float = 0.0
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConformanceResult:
    """Result of a single test vector execution."""

    vector_id: str
    outcome: Outcome
    message: str
    vector_name: str = ""
    expected_result: str | None = None
    actual_result: str | None = None
    expected_error_code: str | None = None
    actual_error_code: str | None = None
    validation_stage: str | None = None
    reason: str | None = None
    duration_ms: float = 0.0
    expected_error: str | None = None
    actual_error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConformanceReport:
    """Aggregate conformance report."""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    results: list[ConformanceResult] = field(default_factory=list)

    def add(self, result: ConformanceResult) -> None:
        """Add a test result to the report."""
        self.results.append(result)
        self.total += 1
        if result.outcome == Outcome.PASS:
            self.passed += 1
        elif result.outcome == Outcome.FAIL:
            self.failed += 1
        elif result.outcome == Outcome.SKIP:
            self.skipped += 1
        else:
            self.errors += 1

    @property
    def success_rate(self) -> float:
        """Calculate success rate (excluding skipped)."""
        executed = self.passed + self.failed
        return (self.passed / executed * 100) if executed > 0 else 0.0

    def summary(self) -> str:
        """Generate summary string."""
        return (
            f"Total: {self.total} | "
            f"Passed: {self.passed} | "
            f"Failed: {self.failed} | "
            f"Skipped: {self.skipped} | "
            f"Errors: {self.errors} | "
            f"Success Rate: {self.success_rate:.1f}%"
        )


# =============================================================================
# Vector Loading
# =============================================================================


@dataclass
class ConformanceVector:
    """A loaded test vector ready for execution."""

    id: str
    name: str
    purpose: str
    folder: Path | None = None
    schema_version: str = "exp_v0.1"
    profile: str = "legacy"
    mode: str = "HARD"
    expected_result: str = "PASS"
    expected_validation_stage: str | None = None
    input_type: str | None = None
    input_path: Path | None = None
    comparison_mode: CompareMode | None = None
    normalize_run_metadata: bool = False
    container: Container | None = None
    loose_path: Path | None = None
    expected: dict[str, Any] = field(default_factory=dict)
    golden_observables: list[dict[str, Any]] = field(default_factory=list)
    golden_path: Path | None = None
    golden_error_code: str | None = None
    golden_validation_stage: str | None = None
    golden_error_message: str | None = None
    golden_error_index: int | None = None
    run_manifest_path: Path | None = None
    trust_policy_path: Path | None = None
    signed_conformance: bool = False
    run_bundle_path: Path | None = None
    bundle_conformance: bool = False
    is_negative: bool = False
    expected_error_code: str | None = None
    required_capabilities: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_source_sink(self) -> tuple[str, str]:
        """Extract source/sink nodes from container or use defaults."""
        # Default node IDs for testing
        return ("source", "sink")

    def to_klein_file(self, path: Path) -> None:
        """
        Export container as a .klein project file for the simulator.

        Creates a minimal graph structure from the payload.
        """
        if not self.container:
            raise ValueError("No container to export")

        # Build minimal .klein structure
        klein_data = {
            "meta": {
                "version": "1.0",
                "target_substrate": self.container.manifest.runtime.target_substrate,
            },
            "nodes": [
                {"id": "source", "type": "Source", "pos": [0, 0, 0]},
                {"id": "sink", "type": "Sink", "pos": [10, 0, 0]},
            ],
            "edges": [
                {"from": "source", "to": "sink", "type": "rail", "impedance": 1.0},
            ],
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(klein_data, f, indent=2)

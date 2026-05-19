"""KCP Conformance Levels Matrix v1 catalog helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path
from typing import Any

from klein.common.hashing import parse_ijson

CATALOG_VERSION = "klein.conformance_levels.v1"
DEFAULT_CATALOG_RELATIVE = Path("specs/catalogs/conformance_levels.v1.json")


class ConformanceLevelError(ValueError):
    """Structured conformance-level catalog or claim failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class LevelReferenceResult:
    """Validation result for declared conformance levels."""

    ok: bool
    declared_levels: list[str]
    verified_levels: list[str]
    catalog_status: str = "not_evaluated"
    dependency_status: str = "not_evaluated"
    error_code: str | None = None
    message: str | None = None


_EMBEDDED_MINIMAL_CATALOG: dict[str, Any] = {
    "catalog_version": CATALOG_VERSION,
    "levels": [
        {
            "level_id": "KCP-Core-HAIL-v1",
            "name": "KCP Core HAIL v1",
            "layer": "CURRENT_ALPHA",
            "category": "core",
            "status": "implemented",
            "requires": [],
            "required_artifacts": ["hail_jsonl"],
            "required_checks": ["hail_schema_valid"],
            "required_tools": ["klein-hail-canon"],
            "evidence": {"specs": ["specs/core/hail-v1.md"], "tests": ["tests/test_hail_core.py"], "fixtures": []},
            "forbidden_claims": ["physical_truth", "hardware_attestation"],
        }
    ],
}


def default_catalog_path() -> Path | None:
    """Return the source-tree canonical catalog path if available."""
    for parent in Path(__file__).resolve().parents:
        candidate = parent / DEFAULT_CATALOG_RELATIVE
        if candidate.exists():
            return candidate
    return None


def load_conformance_level_catalog(path: str | Path | None = None) -> dict[str, Any]:
    """Load the canonical catalog from source or an explicit path."""
    if path is None:
        source_path = default_catalog_path()
        if source_path is not None:
            path = source_path
        else:
            try:
                data = parse_ijson(
                    resources.files("klein")
                    .joinpath("catalogs/conformance_levels.v1.json")
                    .read_text(encoding="utf-8")
                )
                validate_conformance_level_catalog(data)
                return data
            except (FileNotFoundError, ModuleNotFoundError):
                data = _EMBEDDED_MINIMAL_CATALOG
                validate_conformance_level_catalog(data)
                return data
    try:
        data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConformanceLevelError(
            "CONFORMANCE_LEVEL_CATALOG_INVALID",
            f"conformance level catalog JSON parse failed: {exc}",
        ) from exc
    validate_conformance_level_catalog(data)
    return data


def validate_conformance_level_catalog(data: Any) -> None:
    """Validate catalog shape, uniqueness, dependencies, and cycles."""
    if not isinstance(data, dict) or data.get("catalog_version") != CATALOG_VERSION:
        raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", "invalid catalog_version")
    levels = data.get("levels")
    if not isinstance(levels, list) or not levels:
        raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", "levels must be non-empty")
    by_id: dict[str, dict[str, Any]] = {}
    for level in levels:
        _validate_level_shape(level)
        level_id = level["level_id"]
        if level_id in by_id:
            raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", f"duplicate level_id: {level_id}")
        by_id[level_id] = level
    for level_id, level in by_id.items():
        for dependency in level["requires"]:
            if dependency not in by_id:
                raise ConformanceLevelError(
                    "CONFORMANCE_LEVEL_UNKNOWN",
                    f"{level_id} requires unknown level {dependency}",
                )
            if level["layer"] == "CURRENT_ALPHA" and by_id[dependency]["status"] == "future":
                raise ConformanceLevelError(
                    "CONFORMANCE_LEVEL_CLAIM_INVALID",
                    f"{level_id} cannot require future-only level {dependency}",
                )
        if level["status"] == "implemented":
            evidence = level["evidence"]
            if not (evidence["specs"] or evidence["tests"] or evidence["fixtures"]):
                raise ConformanceLevelError(
                    "CONFORMANCE_LEVEL_CATALOG_INVALID",
                    f"implemented level lacks evidence: {level_id}",
                )
    _assert_acyclic(by_id)


def get_conformance_level(level_id: str, catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a level by id or raise `CONFORMANCE_LEVEL_UNKNOWN`."""
    catalog = catalog or load_conformance_level_catalog()
    for level in catalog["levels"]:
        if level["level_id"] == level_id:
            return level
    raise ConformanceLevelError("CONFORMANCE_LEVEL_UNKNOWN", f"unknown conformance level: {level_id}")


def validate_level_references(
    level_ids: list[str],
    catalog: dict[str, Any] | None = None,
    *,
    allow_target_claims: bool = False,
) -> LevelReferenceResult:
    """Validate declared level ids against status and dependency closure."""
    catalog = catalog or load_conformance_level_catalog()
    by_id = {level["level_id"]: level for level in catalog["levels"]}
    declared = list(level_ids)
    declared_set = set(declared)
    if len(declared_set) != len(declared):
        return _level_failure(declared, "CONFORMANCE_LEVEL_CLAIM_INVALID", "duplicate declared conformance level")
    for level_id in declared:
        level = by_id.get(level_id)
        if level is None:
            return _level_failure(declared, "CONFORMANCE_LEVEL_UNKNOWN", f"unknown conformance level: {level_id}")
        if level["status"] == "future":
            return _level_failure(declared, "CONFORMANCE_LEVEL_FUTURE_UNSUPPORTED", f"future level cannot be claimed: {level_id}")
        if level["status"] == "target" and not allow_target_claims:
            return _level_failure(declared, "CONFORMANCE_LEVEL_TARGET_UNSUPPORTED", f"target level cannot be claimed: {level_id}")
    for level_id in declared:
        missing = [dep for dep in by_id[level_id]["requires"] if dep not in declared_set]
        if missing:
            return _level_failure(
                declared,
                "CONFORMANCE_LEVEL_DEPENDENCY_MISSING",
                f"{level_id} missing required level(s): {', '.join(missing)}",
            )
    return LevelReferenceResult(
        ok=True,
        declared_levels=declared,
        verified_levels=declared,
        catalog_status="pass",
        dependency_status="pass",
    )


def classify_levels(level_ids: list[str], catalog: dict[str, Any] | None = None) -> dict[str, list[str]]:
    """Group declared level ids by catalog status."""
    catalog = catalog or load_conformance_level_catalog()
    grouped: dict[str, list[str]] = {"implemented": [], "partial": [], "target": [], "future": []}
    for level_id in level_ids:
        level = get_conformance_level(level_id, catalog)
        grouped[level["status"]].append(level_id)
    return grouped


def verify_capability_declared_levels(
    declaration: dict[str, Any],
    catalog: dict[str, Any] | None = None,
    *,
    allow_target_claims: bool = False,
) -> LevelReferenceResult:
    """Validate `supported_conformance_levels` from a capability declaration."""
    payload = declaration.get("payload") if isinstance(declaration, dict) else None
    if not isinstance(payload, dict):
        return _level_failure([], "CONFORMANCE_LEVEL_CLAIM_INVALID", "capability declaration payload missing")
    levels = payload.get("supported_conformance_levels")
    if not isinstance(levels, list) or not all(isinstance(level, str) and level for level in levels):
        return _level_failure([], "CONFORMANCE_LEVEL_CLAIM_INVALID", "supported_conformance_levels must be strings")
    return validate_level_references(levels, catalog, allow_target_claims=allow_target_claims)


def _validate_level_shape(level: Any) -> None:
    if not isinstance(level, dict):
        raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", "level must be an object")
    required = [
        "level_id",
        "name",
        "layer",
        "category",
        "status",
        "requires",
        "required_artifacts",
        "required_checks",
        "evidence",
        "forbidden_claims",
    ]
    for field in required:
        if field not in level:
            raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", f"level missing {field}")
    for field in ("level_id", "name", "layer", "category", "status"):
        if not isinstance(level[field], str) or not level[field]:
            raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", f"level.{field} must be a string")
    if level["layer"] not in {"CURRENT_ALPHA", "TARGET_V1", "LONG_HORIZON"}:
        raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", f"invalid layer: {level['layer']}")
    if level["category"] not in {"core", "profile", "verifier", "hardware", "recovery"}:
        raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", f"invalid category: {level['category']}")
    if level["status"] not in {"implemented", "partial", "target", "future"}:
        raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", f"invalid status: {level['status']}")
    for field in ("requires", "required_artifacts", "required_checks", "forbidden_claims"):
        if not isinstance(level[field], list) or not all(isinstance(item, str) for item in level[field]):
            raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", f"level.{field} must be a string array")
    evidence = level["evidence"]
    if not isinstance(evidence, dict):
        raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", "level.evidence must be an object")
    for field in ("specs", "tests", "fixtures"):
        if not isinstance(evidence.get(field), list) or not all(isinstance(item, str) for item in evidence[field]):
            raise ConformanceLevelError("CONFORMANCE_LEVEL_CATALOG_INVALID", f"level.evidence.{field} must be a string array")


def _assert_acyclic(by_id: dict[str, dict[str, Any]]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(level_id: str) -> None:
        if level_id in visited:
            return
        if level_id in visiting:
            raise ConformanceLevelError("CONFORMANCE_LEVEL_CYCLE", f"cycle includes {level_id}")
        visiting.add(level_id)
        for dependency in by_id[level_id]["requires"]:
            visit(dependency)
        visiting.remove(level_id)
        visited.add(level_id)

    for level_id in by_id:
        visit(level_id)


def _level_failure(declared: list[str], error_code: str, message: str) -> LevelReferenceResult:
    return LevelReferenceResult(
        ok=False,
        declared_levels=declared,
        verified_levels=[],
        catalog_status="fail" if error_code in {"CONFORMANCE_LEVEL_CATALOG_INVALID", "CONFORMANCE_LEVEL_UNKNOWN"} else "pass",
        dependency_status="fail",
        error_code=error_code,
        message=message,
    )

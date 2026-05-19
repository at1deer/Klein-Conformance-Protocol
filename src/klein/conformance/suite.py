"""Vector suite loading, v1 contract validation, and legacy discovery."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from klein.common.models import Container
from klein.conformance.errors import (
    DEFAULT_LEGACY_SUITE_DIR,
    DEFAULT_V1_SUITE_DIR,
    HAIL_GOLDEN_SCHEMA_INVALID,
    VECTOR_INDEX_INVALID,
    VECTOR_INPUT_MISSING,
    VECTOR_METADATA_INVALID,
)
from klein.conformance.models import CompareMode, ConformanceVector, VectorLoadError
from klein.hail.validation import parse_jsonl_events


def load_index(index_path: Path) -> dict[str, Any]:
    """Load the test vector index."""
    if not index_path.exists():
        return {"index": {"kaps": []}, "kaps_combined": []}
    with open(index_path, encoding="utf-8") as f:
        return json.load(f)


def load_klnc(path: Path) -> Container:
    """Load a .kleinc/.klnc container file."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return Container.model_validate(data)


def load_loose_vector(path: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    """
    Load a loose format vector.

    Returns:
        Tuple of (manifest, expected, golden_observables)
    """
    manifest_path = path / "manifest.json"
    expected_path = path / "expected" / "expected.json"
    golden_path = path / "golden" / "observables.jsonl"

    manifest = {}
    expected = {}
    golden = []

    if manifest_path.exists():
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)

    if expected_path.exists():
        with open(expected_path, encoding="utf-8") as f:
            expected = json.load(f)

    if golden_path.exists():
        with open(golden_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    golden.append(json.loads(line))

    return manifest, expected, golden


def load_expected_file(folder: Path) -> dict[str, Any]:
    """Load expected/expected.json when present."""
    expected_path = folder / "expected" / "expected.json"
    if not expected_path.exists():
        return {}
    with open(expected_path, encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def load_vector_metadata(folder: Path, index_item: dict[str, Any]) -> dict[str, Any]:
    """Load v1 vector metadata, allowing folder-local vector.json to override index data."""
    metadata = dict(index_item)
    vector_path = folder / "vector.json"
    if vector_path.exists():
        with open(vector_path, encoding="utf-8") as f:
            folder_metadata = json.load(f)
        metadata.update(folder_metadata)
    return metadata


def resolve_vector_input_path(folder: Path, metadata: dict[str, Any]) -> Path | None:
    """Resolve a declared v1 vector input path relative to the vector folder."""
    input_path = metadata.get("input_path")
    if not input_path:
        return None
    path = Path(str(input_path))
    if path.is_absolute():
        return path
    return folder / path


def resolve_optional_vector_path(folder: Path, metadata: dict[str, Any], field: str) -> Path | None:
    """Resolve an optional vector-local path while keeping it inside the vector folder."""
    value = metadata.get(field)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector optional path field {field} must be a non-empty string",
            detail={"field": field, "value": value},
        )
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector optional path field {field} must be relative and stay inside the vector folder",
            detail={"field": field, "value": value},
        )
    return folder / path


_VALID_MODES = {"HARD", "ENVELOPE", "DIAGNOSTIC"}
_VALID_RESULTS = {"PASS", "FAIL"}
_VALID_INPUT_TYPES = {"project", "container", "hail_jsonl", "invalid_artifact"}
_VALID_STAGES = {
    "vector_index",
    "vector_metadata",
    "vector_input",
    "artifact_parse",
    "artifact_schema",
    "payload_validation",
    "json_parse",
    "hail_schema",
    "golden_schema",
    "signed_conformance",
    "bundle_conformance",
}

_VECTOR_SUPPORT_DIRS = {"input", "expected", "golden", "manifest", "bundle"}


def _load_json_object(path: Path, *, error_code: str, stage: str) -> dict[str, Any]:
    """Load a JSON object or raise a structured vector metadata error."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise VectorLoadError(
            error_code,
            f"{path} is not valid JSON: {exc}",
            validation_stage=stage,
            detail={"path": str(path), "line": exc.lineno, "column": exc.colno},
        ) from exc
    if not isinstance(data, dict):
        raise VectorLoadError(
            error_code,
            f"{path} must contain a JSON object",
            validation_stage=stage,
            detail={"path": str(path)},
        )
    return data


def _validate_relative_folder(folder_value: Any, *, vector_id: str) -> str:
    """Validate an index folder value and return it as a relative string."""
    if not isinstance(folder_value, str) or not folder_value:
        raise VectorLoadError(
            VECTOR_INDEX_INVALID,
            f"Vector {vector_id} must declare a non-empty folder",
            validation_stage="vector_index",
        )
    folder_path = Path(folder_value)
    if folder_path.is_absolute() or ".." in folder_path.parts:
        raise VectorLoadError(
            VECTOR_INDEX_INVALID,
            f"Vector {vector_id} folder must be relative and stay inside the suite",
            validation_stage="vector_index",
            detail={"folder": folder_value},
        )
    return folder_value


def validate_v1_index(index: dict[str, Any], suite_dir: Path) -> list[dict[str, str]]:
    """Validate a v1 index.json and return normalized id/folder entries."""
    vectors = index.get("vectors")
    if not isinstance(vectors, list):
        raise VectorLoadError(
            VECTOR_INDEX_INVALID,
            "v1 index.json must contain vectors as a list",
            validation_stage="vector_index",
        )

    seen: set[str] = set()
    normalized: list[dict[str, str]] = []
    for position, item in enumerate(vectors):
        if not isinstance(item, dict):
            raise VectorLoadError(
                VECTOR_INDEX_INVALID,
                f"v1 index vector entry at position {position} must be an object",
                validation_stage="vector_index",
                detail={"position": position},
            )
        vector_id = item.get("id")
        if not isinstance(vector_id, str) or not vector_id:
            raise VectorLoadError(
                VECTOR_INDEX_INVALID,
                f"v1 index vector entry at position {position} must include id",
                validation_stage="vector_index",
                detail={"position": position},
            )
        if vector_id in seen:
            raise VectorLoadError(
                VECTOR_INDEX_INVALID,
                f"Duplicate v1 vector id: {vector_id}",
                validation_stage="vector_index",
                detail={"id": vector_id},
            )
        seen.add(vector_id)
        folder_value = _validate_relative_folder(item.get("folder"), vector_id=vector_id)
        folder = suite_dir / folder_value
        if not folder.exists() or not folder.is_dir():
            raise VectorLoadError(
                VECTOR_INDEX_INVALID,
                f"Vector {vector_id} folder does not exist: {folder}",
                validation_stage="vector_index",
                detail={"id": vector_id, "folder": str(folder)},
            )
        vector_json = folder / "vector.json"
        if not vector_json.exists():
            raise VectorLoadError(
                VECTOR_INDEX_INVALID,
                f"Vector {vector_id} is missing vector.json",
                validation_stage="vector_index",
                detail={"id": vector_id, "path": str(vector_json)},
            )
        normalized.append({"id": vector_id, "folder": folder_value})
    return normalized


def validate_v1_metadata(metadata: dict[str, Any], *, folder: Path, index_id: str) -> None:
    """Validate one v1 vector.json metadata object."""
    required_strings = ["id", "name", "schema_version", "profile", "mode", "expected_result"]
    for key in required_strings:
        if not isinstance(metadata.get(key), str) or not metadata.get(key):
            raise VectorLoadError(
                VECTOR_METADATA_INVALID,
                f"Vector {index_id} metadata missing required string field {key}",
                detail={"id": index_id, "field": key, "folder": str(folder)},
            )
    if metadata["id"] != index_id:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector id mismatch: index has {index_id}, vector.json has {metadata['id']}",
            detail={"index_id": index_id, "metadata_id": metadata["id"]},
        )
    if metadata["schema_version"] != "v1":
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} schema_version must be v1",
            detail={"id": index_id, "schema_version": metadata["schema_version"]},
        )
    if metadata["mode"] not in _VALID_MODES:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} mode must be one of {sorted(_VALID_MODES)}",
            detail={"id": index_id, "mode": metadata["mode"]},
        )
    if metadata["expected_result"] not in _VALID_RESULTS:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} expected_result must be PASS or FAIL",
            detail={"id": index_id, "expected_result": metadata["expected_result"]},
        )
    if metadata["profile"] == "dmf" and metadata.get("profile_version") != "v1":
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} DMF profile vectors must declare profile_version v1",
            detail={"id": index_id, "profile_version": metadata.get("profile_version")},
        )
    if metadata.get("input_type") not in _VALID_INPUT_TYPES:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} input_type must be one of {sorted(_VALID_INPUT_TYPES)}",
            detail={"id": index_id, "input_type": metadata.get("input_type")},
        )
    input_path = metadata.get("input_path")
    if not isinstance(input_path, str) or not input_path:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} must declare input_path",
            detail={"id": index_id},
        )
    resolved_input = Path(input_path)
    if resolved_input.is_absolute() or ".." in resolved_input.parts:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} input_path must be relative and stay inside the vector folder",
            detail={"id": index_id, "input_path": input_path},
        )
    try:
        CompareMode(str(metadata.get("comparison_mode")))
    except ValueError as exc:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} comparison_mode is invalid",
            detail={"id": index_id, "comparison_mode": metadata.get("comparison_mode")},
        ) from exc
    if metadata["expected_result"] == "FAIL" and not metadata.get("expected_error_code"):
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Negative vector {index_id} must declare expected_error_code",
            detail={"id": index_id},
        )
    resolve_optional_vector_path(folder, metadata, "run_manifest_path")
    resolve_optional_vector_path(folder, metadata, "trust_policy_path")
    resolve_optional_vector_path(folder, metadata, "run_bundle_path")
    signed_conformance = metadata.get("signed_conformance", False)
    if not isinstance(signed_conformance, bool):
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} signed_conformance must be a boolean",
            detail={"id": index_id, "signed_conformance": signed_conformance},
        )
    if signed_conformance:
        for field in ("run_manifest_path", "trust_policy_path"):
            if not metadata.get(field):
                raise VectorLoadError(
                    VECTOR_METADATA_INVALID,
                    f"Vector {index_id} signed_conformance requires {field}",
                    detail={"id": index_id, "field": field},
                )
    bundle_conformance = metadata.get("bundle_conformance", False)
    if not isinstance(bundle_conformance, bool):
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} bundle_conformance must be a boolean",
            detail={"id": index_id, "bundle_conformance": bundle_conformance},
        )
    if bundle_conformance and not metadata.get("run_bundle_path"):
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} bundle_conformance requires run_bundle_path",
            detail={"id": index_id, "field": "run_bundle_path"},
        )
    assertions = metadata.get("evidence_assertions", [])
    if assertions is not None:
        if not isinstance(assertions, list):
            raise VectorLoadError(
                VECTOR_METADATA_INVALID,
                f"Vector {index_id} evidence_assertions must be a list",
                detail={"id": index_id},
            )
        for assertion_index, assertion in enumerate(assertions):
            if not isinstance(assertion, dict):
                raise VectorLoadError(
                    VECTOR_METADATA_INVALID,
                    f"Vector {index_id} evidence assertion must be an object",
                    detail={"id": index_id, "assertion_index": assertion_index},
                )
            if "kind" in assertion and not isinstance(assertion["kind"], str):
                raise VectorLoadError(
                    VECTOR_METADATA_INVALID,
                    f"Vector {index_id} evidence assertion kind must be a string",
                    detail={"id": index_id, "assertion_index": assertion_index},
                )
            where = assertion.get("where", {})
            if not isinstance(where, dict):
                raise VectorLoadError(
                    VECTOR_METADATA_INVALID,
                    f"Vector {index_id} evidence assertion where must be an object",
                    detail={"id": index_id, "assertion_index": assertion_index},
                )
    stage = metadata.get("expected_validation_stage")
    if stage is not None and stage not in _VALID_STAGES:
        raise VectorLoadError(
            VECTOR_METADATA_INVALID,
            f"Vector {index_id} has unknown expected_validation_stage",
            detail={"id": index_id, "stage": stage},
        )


def load_v1_golden(
    folder: Path,
) -> tuple[
    list[dict[str, Any]],
    Path | None,
    str | None,
    str | None,
    str | None,
    int | None,
]:
    """Load and validate a v1 golden HAIL JSONL stream if present."""
    golden_path = folder / "golden" / "observables.jsonl"
    if not golden_path.exists():
        return [], golden_path, None, None, None, None

    validation, events = parse_jsonl_events(golden_path.read_text(encoding="utf-8"))
    if not validation.ok:
        return (
            events,
            golden_path,
            HAIL_GOLDEN_SCHEMA_INVALID,
            validation.validation_stage,
            validation.message,
            validation.index,
        )
    return events, golden_path, None, None, None, None


def resolve_suite_dir(suite_dir: Path | None = None, *, legacy: bool = False) -> Path:
    """Resolve the requested conformance suite directory."""
    if suite_dir is not None:
        return suite_dir
    if legacy:
        return DEFAULT_LEGACY_SUITE_DIR
    if DEFAULT_V1_SUITE_DIR.exists():
        return DEFAULT_V1_SUITE_DIR
    return DEFAULT_LEGACY_SUITE_DIR


def load_v1_suite(suite_dir: Path, vector_ids: list[str] | None = None) -> list[ConformanceVector]:
    """Load explicitly versioned v1 conformance vectors."""
    index = _load_json_object(
        suite_dir / "index.json",
        error_code=VECTOR_INDEX_INVALID,
        stage="vector_index",
    )
    index_entries = validate_v1_index(index, suite_dir)
    vectors: list[ConformanceVector] = []

    for item in index_entries:
        vid = item["id"]
        if vector_ids and vid not in vector_ids:
            continue

        folder = suite_dir / item["folder"]
        metadata = load_vector_metadata(folder, item)
        validate_v1_metadata(metadata, folder=folder, index_id=vid)
        expected = load_expected_file(folder)
        golden, golden_path, golden_error_code, golden_stage, golden_message, golden_index = (
            load_v1_golden(folder)
        )
        expected_result = metadata.get("expected_result", expected.get("expected_result", "PASS"))
        expected_error_code = metadata.get(
            "expected_error_code",
            expected.get("expected_error_code"),
        )
        comparison_mode_name = metadata.get(
            "comparison_mode",
            expected.get("comparison_mode", "EXACT_JSONL"),
        )

        vectors.append(
            ConformanceVector(
                id=vid,
                name=metadata.get("name", folder.name),
                purpose=metadata.get("purpose", ""),
                folder=folder,
                schema_version=metadata.get("schema_version", "v1"),
                profile=metadata.get("profile", "core"),
                mode=metadata.get("mode", expected.get("mode", "HARD")),
                expected_result=expected_result,
                expected_validation_stage=metadata.get(
                    "expected_validation_stage",
                    expected.get("expected_validation_stage"),
                ),
                input_type=metadata.get("input_type"),
                input_path=resolve_vector_input_path(folder, metadata),
                run_manifest_path=resolve_optional_vector_path(
                    folder,
                    metadata,
                    "run_manifest_path",
                ),
                trust_policy_path=resolve_optional_vector_path(
                    folder,
                    metadata,
                    "trust_policy_path",
                ),
                signed_conformance=bool(metadata.get("signed_conformance", False)),
                run_bundle_path=resolve_optional_vector_path(
                    folder,
                    metadata,
                    "run_bundle_path",
                ),
                bundle_conformance=bool(metadata.get("bundle_conformance", False)),
                comparison_mode=CompareMode(comparison_mode_name),
                normalize_run_metadata=bool(metadata.get("normalize_run_metadata", False)),
                loose_path=folder if folder.exists() else None,
                expected=expected,
                golden_observables=golden,
                golden_path=golden_path,
                golden_error_code=golden_error_code,
                golden_validation_stage=golden_stage,
                golden_error_message=golden_message,
                golden_error_index=golden_index,
                is_negative=expected_result == "FAIL",
                expected_error_code=expected_error_code,
                required_capabilities=metadata.get("required_capabilities", []),
                metadata=metadata,
            )
        )

    vectors.sort(key=lambda v: v.id)
    return vectors


def check_v1_suite_integrity(suite_dir: Path) -> list[dict[str, Any]]:
    """Return structural integrity issues for an authoritative v1 vector suite."""
    issues: list[dict[str, Any]] = []
    try:
        index = _load_json_object(
            suite_dir / "index.json",
            error_code=VECTOR_INDEX_INVALID,
            stage="vector_index",
        )
    except VectorLoadError as exc:
        return [{
            "code": exc.error_code,
            "message": str(exc),
            "detail": exc.detail,
        }]

    raw_vectors = index.get("vectors")
    if not isinstance(raw_vectors, list):
        return [{
            "code": VECTOR_INDEX_INVALID,
            "message": "v1 index.json must contain vectors as a list",
            "detail": {"path": str(suite_dir / "index.json")},
        }]

    seen_ids: dict[str, int] = {}
    seen_folders: dict[str, str] = {}
    seen_names: dict[str, str] = {}
    indexed_folders: set[str] = set()

    for position, item in enumerate(raw_vectors):
        if not isinstance(item, dict):
            issues.append({
                "code": VECTOR_INDEX_INVALID,
                "message": "v1 index vectors entries must be objects",
                "detail": {"position": position, "entry": item},
            })
            continue
        vector_id = item.get("id")
        folder_value = item.get("folder")
        if not isinstance(vector_id, str) or not vector_id:
            issues.append({
                "code": VECTOR_INDEX_INVALID,
                "message": "v1 index vector entry missing id",
                "detail": {"position": position, "entry": item},
            })
            continue
        if vector_id in seen_ids:
            issues.append({
                "code": VECTOR_INDEX_INVALID,
                "message": f"Duplicate v1 vector id {vector_id}",
                "detail": {"id": vector_id, "first_position": seen_ids[vector_id], "position": position},
            })
        seen_ids.setdefault(vector_id, position)

        try:
            folder_rel = _validate_relative_folder(folder_value, vector_id=vector_id)
        except VectorLoadError as exc:
            issues.append({"code": exc.error_code, "message": str(exc), "detail": exc.detail})
            continue
        if folder_rel in seen_folders:
            issues.append({
                "code": VECTOR_INDEX_INVALID,
                "message": f"Duplicate v1 vector folder {folder_rel}",
                "detail": {"folder": folder_rel, "first_id": seen_folders[folder_rel], "id": vector_id},
            })
        seen_folders.setdefault(folder_rel, vector_id)
        indexed_folders.add(folder_rel)

        folder = suite_dir / folder_rel
        vector_json = folder / "vector.json"
        if not folder.exists():
            issues.append({
                "code": VECTOR_INDEX_INVALID,
                "message": f"Referenced vector folder does not exist: {folder_rel}",
                "detail": {"id": vector_id, "folder": folder_rel},
            })
            continue
        if not vector_json.exists():
            issues.append({
                "code": VECTOR_INDEX_INVALID,
                "message": f"Referenced vector folder is missing vector.json: {folder_rel}",
                "detail": {"id": vector_id, "folder": folder_rel},
            })
            continue

        try:
            metadata = _load_json_object(
                vector_json,
                error_code=VECTOR_METADATA_INVALID,
                stage="vector_metadata",
            )
            validate_v1_metadata(metadata, folder=folder, index_id=vector_id)
        except VectorLoadError as exc:
            issues.append({"code": exc.error_code, "message": str(exc), "detail": exc.detail})
            continue

        name = metadata.get("name")
        if isinstance(name, str):
            if name in seen_names:
                issues.append({
                    "code": VECTOR_METADATA_INVALID,
                    "message": f"Duplicate v1 vector name {name}",
                    "detail": {"name": name, "first_id": seen_names[name], "id": vector_id},
                })
            seen_names.setdefault(name, vector_id)

        input_path = resolve_vector_input_path(folder, metadata)
        missing_input_allowed = (
            metadata.get("expected_result") == "FAIL"
            and metadata.get("expected_error_code") == VECTOR_INPUT_MISSING
        )
        if input_path is None or not input_path.exists():
            if not missing_input_allowed:
                issues.append({
                    "code": VECTOR_METADATA_INVALID,
                    "message": f"v1 vector input_path is missing: {vector_id}",
                    "detail": {
                        "id": vector_id,
                        "input_path": metadata.get("input_path"),
                    },
                })
        try:
            run_manifest_path = resolve_optional_vector_path(folder, metadata, "run_manifest_path")
        except VectorLoadError as exc:
            issues.append({"code": exc.error_code, "message": str(exc), "detail": exc.detail})
            run_manifest_path = None
        if run_manifest_path is not None and not run_manifest_path.exists():
            issues.append({
                "code": VECTOR_METADATA_INVALID,
                "message": f"v1 vector run_manifest_path is missing: {vector_id}",
                "detail": {
                    "id": vector_id,
                    "run_manifest_path": metadata.get("run_manifest_path"),
                },
            })
        try:
            trust_policy_path = resolve_optional_vector_path(folder, metadata, "trust_policy_path")
        except VectorLoadError as exc:
            issues.append({"code": exc.error_code, "message": str(exc), "detail": exc.detail})
            trust_policy_path = None
        if trust_policy_path is not None and not trust_policy_path.exists():
            issues.append({
                "code": VECTOR_METADATA_INVALID,
                "message": f"v1 vector trust_policy_path is missing: {vector_id}",
                "detail": {
                    "id": vector_id,
                    "trust_policy_path": metadata.get("trust_policy_path"),
                },
            })

        golden_path = folder / "golden" / "observables.jsonl"
        if metadata.get("expected_result") != "FAIL":
            if not golden_path.exists():
                issues.append({
                    "code": HAIL_GOLDEN_SCHEMA_INVALID,
                    "message": f"Positive v1 vector is missing golden HAIL: {vector_id}",
                    "detail": {"id": vector_id, "path": str(golden_path)},
                })
            else:
                _, _, error_code, message, stage, index = load_v1_golden(folder)
                if error_code:
                    issues.append({
                        "code": error_code,
                        "message": message or "Positive v1 golden HAIL failed validation",
                        "detail": {"id": vector_id, "stage": stage, "line_index": index},
                    })

    for folder in _candidate_vector_folders(suite_dir):
        folder_rel = folder.relative_to(suite_dir).as_posix()
        if folder_rel not in indexed_folders and not (folder / ".not-a-vector").exists():
            issues.append({
                "code": VECTOR_INDEX_INVALID,
                "message": f"Unindexed v1 vector directory: {folder_rel}",
                "detail": {"folder": folder_rel},
            })
    return issues


def _candidate_vector_folders(suite_dir: Path) -> list[Path]:
    """Return directories that look like vector folders, excluding support dirs."""
    candidates: list[Path] = []
    if not suite_dir.exists():
        return candidates
    for folder in suite_dir.rglob("*"):
        if not folder.is_dir():
            continue
        rel_parts = folder.relative_to(suite_dir).parts
        if not rel_parts or len(rel_parts) == 1:
            continue
        if any(part in _VECTOR_SUPPORT_DIRS for part in rel_parts):
            continue
        candidates.append(folder)
    return candidates


def discover_vectors(
    vector_ids: list[str] | None = None,
    category: str | None = None,
    suite_dir: Path | None = None,
    legacy: bool = False,
) -> list[ConformanceVector]:
    """
    Discover and load test vectors.

    Args:
        vector_ids: Specific vector IDs to load (e.g., ["001", "N003"])
        category: Filter by category ("positive", "negative", "all")

    Returns:
        List of ConformanceVector objects
    """
    suite_path = resolve_suite_dir(suite_dir, legacy=legacy)
    index = load_index(suite_path / "index.json")
    if "vectors" in index:
        vectors = load_v1_suite(suite_path, vector_ids)
        if category == "positive":
            vectors = [v for v in vectors if not v.is_negative]
        elif category == "negative":
            vectors = [v for v in vectors if v.is_negative]
        return vectors

    vectors: list[ConformanceVector] = []
    kap_dir = suite_path / "kap"
    loose_dir = suite_path / "loose"

    # Build negative test lookup
    negative_lookup: dict[str, str] = {}
    for neg in index.get("index", {}).get("negative_tests", []):
        negative_lookup[neg["id"]] = neg.get("expected_error_code", "")

    # Get all KAP entries
    kaps = index.get("kaps_combined", []) or index.get("index", {}).get("kaps", [])

    for kap in kaps:
        vid = kap.get("id", "")

        # Filter by vector_ids if specified
        if vector_ids and vid not in vector_ids:
            continue

        # Determine if negative test
        is_negative = vid in negative_lookup

        # Filter by category
        if category == "positive" and is_negative:
            continue
        if category == "negative" and not is_negative:
            continue

        # Try to load .kleinc/.klnc container first
        klnc_path = kap_dir / kap.get("file", "").split("/")[-1]
        container = None
        if klnc_path.exists():
            try:
                container = load_klnc(klnc_path)
            except Exception:  # noqa: B110 - malformed legacy containers are skipped.
                pass

        # Try loose format
        loose_path = None
        expected = {}
        golden = []

        # Find matching loose folder
        for folder in loose_dir.iterdir() if loose_dir.exists() else []:
            if folder.is_dir() and folder.name.startswith(f"{vid}_"):
                loose_path = folder
                _, expected, golden = load_loose_vector(folder)
                break

        vector = ConformanceVector(
            id=vid,
            name=kap.get("file", "").split("/")[-1],
            purpose=kap.get("purpose", ""),
            schema_version=index.get("index", {}).get("version", "exp_v0.1"),
            profile="legacy",
            expected_result="FAIL" if is_negative else "PASS",
            container=container,
            loose_path=loose_path,
            expected=expected,
            golden_observables=golden,
            is_negative=is_negative,
            expected_error_code=negative_lookup.get(vid),
        )
        vectors.append(vector)

    # Sort by ID
    vectors.sort(key=lambda v: v.id)
    return vectors


# =============================================================================

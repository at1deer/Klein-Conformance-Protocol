"""Portable Klein artifact validation and hashing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from klein.common.hashing import HashResult, hash_json_artifact, parse_ijson
from klein.common.models import Container, KleinProject
from klein.profiles.dmf import DMFProfileContext
from klein.profiles.dmf.validation import validate_dmf_payload


class ArtifactValidationError(ValueError):
    """Structured artifact validation failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class ArtifactValidationResult:
    """Result for project/container validation."""

    ok: bool
    artifact_type: str
    artifact_form: str | None = None
    profile_id: str | None = None
    profile_version: str | None = None
    mode: str | None = None
    error_code: str | None = None
    message: str | None = None


def load_json_artifact(path: str | Path) -> dict[str, Any]:
    """Load artifact JSON as Klein I-JSON."""
    try:
        data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ArtifactValidationError("ARTIFACT_JSON_INVALID", f"artifact JSON parse failed: {exc}") from exc
    if not isinstance(data, dict):
        raise ArtifactValidationError("ARTIFACT_INVALID", "artifact root must be a JSON object")
    return data


def detect_artifact_type(path_or_data: str | Path | dict[str, Any]) -> str:
    """Detect a Klein artifact type from path suffix or object shape."""
    if isinstance(path_or_data, str | Path):
        suffix = Path(path_or_data).suffix.lower()
        if suffix == ".klein":
            return "project"
        if suffix == ".kleinc":
            return "container"
        data = load_json_artifact(path_or_data)
    else:
        data = path_or_data
    if data.get("kind") == "KLEIN_PROJECT" or {"meta", "nodes", "edges"} <= set(data):
        return "project"
    if data.get("kind") == "KLEIN_CONTAINER" or "klein_container_version" in data:
        return "container"
    raise ArtifactValidationError("ARTIFACT_UNSUPPORTED_KIND", "unsupported artifact kind")


def canonical_artifact_hash(path_or_data: str | Path | dict[str, Any]) -> HashResult:
    """Return canonical artifact hash using Klein canonical JSON v1."""
    if isinstance(path_or_data, str | Path):
        return hash_json_artifact(Path(path_or_data))
    return _hash_json_value(path_or_data)


def validate_klein_project(data: dict[str, Any]) -> ArtifactValidationResult:
    """Validate a `.klein` project in canonical or compatibility form."""
    if data.get("kind") == "KLEIN_PROJECT":
        return _validate_canonical_project(data)
    if {"meta", "nodes", "edges"} <= set(data):
        try:
            KleinProject.model_validate(data)
        except ValidationError as exc:
            return _artifact_failure("project", "graph", "ARTIFACT_SCHEMA_INVALID", str(exc))
        return ArtifactValidationResult(
            ok=True,
            artifact_type="project",
            artifact_form="graph",
            profile_id=None,
            profile_version=None,
            mode=None,
        )
    return _artifact_failure("project", None, "ARTIFACT_UNSUPPORTED_KIND", "unsupported project artifact shape")


def load_klein_project(path: str | Path) -> dict[str, Any]:
    """Load and validate a `.klein` project."""
    data = load_json_artifact(path)
    result = validate_klein_project(data)
    if not result.ok:
        raise ArtifactValidationError(result.error_code or "ARTIFACT_SCHEMA_INVALID", result.message or "project invalid")
    return data


def validate_klein_container(data: dict[str, Any]) -> ArtifactValidationResult:
    """Validate a `.kleinc` container in current or canonical form."""
    if data.get("kind") == "KLEIN_CONTAINER":
        return _validate_canonical_container(data)
    if "klein_container_version" in data:
        return _validate_current_container(data)
    return _artifact_failure("container", None, "ARTIFACT_UNSUPPORTED_KIND", "unsupported container artifact shape")


def load_klein_container(path: str | Path) -> dict[str, Any]:
    """Load and validate a `.kleinc` container."""
    data = load_json_artifact(path)
    result = validate_klein_container(data)
    if not result.ok:
        raise ArtifactValidationError(result.error_code or "ARTIFACT_SCHEMA_INVALID", result.message or "container invalid")
    return data


def validate_artifact(path_or_data: str | Path | dict[str, Any]) -> ArtifactValidationResult:
    """Validate any supported Klein project/container artifact."""
    data = load_json_artifact(path_or_data) if isinstance(path_or_data, str | Path) else path_or_data
    artifact_type = detect_artifact_type(data)
    if artifact_type == "project":
        return validate_klein_project(data)
    if artifact_type == "container":
        return validate_klein_container(data)
    return _artifact_failure(artifact_type, None, "ARTIFACT_UNSUPPORTED_KIND", "unsupported artifact type")


def _validate_canonical_project(data: dict[str, Any]) -> ArtifactValidationResult:
    if data.get("schema_version") != "v1":
        return _artifact_failure("project", "canonical", "ARTIFACT_UNSUPPORTED_VERSION", "unsupported project schema_version")
    profile = data.get("profile")
    if not isinstance(profile, dict) or not profile.get("profile_id") or not profile.get("profile_version"):
        return _artifact_failure("project", "canonical", "ARTIFACT_PROFILE_MISSING", "project profile is required")
    mode = data.get("mode")
    if mode not in {"HARD", "ENVELOPE", "DIAGNOSTIC"}:
        return _artifact_failure("project", "canonical", "ARTIFACT_SCHEMA_INVALID", "project mode is invalid")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return _artifact_failure("project", "canonical", "ARTIFACT_PAYLOAD_MISSING", "project payload is required")
    payload_error = _validate_profile_payload(profile["profile_id"], profile["profile_version"], payload)
    if payload_error is not None:
        return _artifact_failure("project", "canonical", payload_error.error_code, str(payload_error))
    return ArtifactValidationResult(True, "project", "canonical", profile["profile_id"], profile["profile_version"], mode)


def _validate_current_container(data: dict[str, Any]) -> ArtifactValidationResult:
    if data.get("klein_container_version") != "1.0":
        return _artifact_failure("container", "current", "ARTIFACT_UNSUPPORTED_VERSION", "unsupported container version")
    payload = data.get("payload")
    if not isinstance(payload, dict):
        return _artifact_failure("container", "current", "ARTIFACT_PAYLOAD_MISSING", "container payload is required")
    payload_error = _validate_profile_payload("dmf", "v1", payload)
    if payload_error is not None:
        return _artifact_failure("container", "current", payload_error.error_code, str(payload_error))
    try:
        Container.model_validate(data)
    except ValidationError as exc:
        return _artifact_failure("container", "current", "ARTIFACT_SCHEMA_INVALID", str(exc))
    manifest = data.get("manifest", {})
    runtime = manifest.get("runtime", {}) if isinstance(manifest, dict) else {}
    mode = runtime.get("mode")
    if not mode:
        return _artifact_failure("container", "current", "ARTIFACT_SCHEMA_INVALID", "container runtime mode is required")
    return ArtifactValidationResult(True, "container", "current", "dmf", "v1", str(mode))


def _validate_canonical_container(data: dict[str, Any]) -> ArtifactValidationResult:
    if data.get("schema_version") != "v1":
        return _artifact_failure("container", "canonical", "ARTIFACT_UNSUPPORTED_VERSION", "unsupported container schema_version")
    profile = data.get("profile")
    if not isinstance(profile, dict) or not profile.get("profile_id") or not profile.get("profile_version"):
        return _artifact_failure("container", "canonical", "ARTIFACT_PROFILE_MISSING", "container profile is required")
    mode = data.get("mode")
    if mode not in {"HARD", "ENVELOPE", "DIAGNOSTIC"}:
        return _artifact_failure("container", "canonical", "ARTIFACT_SCHEMA_INVALID", "container mode is invalid")
    payloads = data.get("payloads")
    if not isinstance(payloads, list) or not payloads:
        return _artifact_failure("container", "canonical", "ARTIFACT_PAYLOAD_MISSING", "container payloads are required")
    for payload in payloads:
        if not isinstance(payload, dict):
            return _artifact_failure("container", "canonical", "ARTIFACT_PAYLOAD_INVALID", "payload entry must be an object")
        normalized = {
            "kind": payload.get("payload_kind"),
            "encoding": "JSON" if payload.get("encoding") == "json" else payload.get("encoding", "JSON"),
            "data": payload.get("data"),
        }
        payload_error = _validate_profile_payload(profile["profile_id"], profile["profile_version"], normalized)
        if payload_error is not None:
            return _artifact_failure("container", "canonical", payload_error.error_code, str(payload_error))
    return ArtifactValidationResult(True, "container", "canonical", profile["profile_id"], profile["profile_version"], mode)


def _validate_profile_payload(
    profile_id: str,
    profile_version: str,
    payload: dict[str, Any],
) -> ArtifactValidationError | None:
    if profile_id != "dmf" or profile_version != "v1":
        return ArtifactValidationError("ARTIFACT_PROFILE_MISMATCH", f"unsupported profile {profile_id}/{profile_version}")
    errors = validate_dmf_payload(payload, DMFProfileContext())
    if errors:
        first = errors[0]
        return ArtifactValidationError(first.code.value, first.message)
    return None


def _artifact_failure(
    artifact_type: str,
    form: str | None,
    error_code: str,
    message: str,
) -> ArtifactValidationResult:
    return ArtifactValidationResult(
        ok=False,
        artifact_type=artifact_type,
        artifact_form=form,
        error_code=error_code,
        message=message,
    )


def _hash_json_value(value: dict[str, Any]) -> HashResult:
    from klein.common.hashing import hash_json_value

    return hash_json_value(value)

"""Strict HAIL v1 validation with explicit legacy normalization helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from pydantic import TypeAdapter, ValidationError

from klein.common.hashing import (
    DuplicateJSONKeyError,
    NonFiniteJSONNumberError,
    object_pairs_no_duplicates,
    reject_non_finite_json_number,
)
from klein.common.models import HAILEvent

HAIL_SCHEMA_INVALID = "HAIL_SCHEMA_INVALID"
HAIL_JSON_INVALID = "HAIL_JSON_INVALID"
HAIL_VALIDATION_STAGE = "hail_schema"

_HAIL_EVENT_ADAPTER = TypeAdapter(HAILEvent)


@dataclass(frozen=True)
class HAILValidationResult:
    """Validation result for one HAIL event or stream."""

    ok: bool
    error_code: str | None = None
    validation_stage: str | None = None
    message: str = ""
    index: int | None = None
    errors: list[dict[str, Any]] = field(default_factory=list)


def validate_event(event: dict[str, Any], *, index: int | None = None) -> HAILValidationResult:
    """Validate one event against the strict HAIL v1 Pydantic union."""
    try:
        _HAIL_EVENT_ADAPTER.validate_python(event)
    except ValidationError as exc:
        return HAILValidationResult(
            ok=False,
            error_code=HAIL_SCHEMA_INVALID,
            validation_stage=HAIL_VALIDATION_STAGE,
            message=str(exc),
            index=index,
            errors=exc.errors(),
        )
    return HAILValidationResult(ok=True, index=index)


def validate_events(events: list[dict[str, Any]]) -> HAILValidationResult:
    """Validate a HAIL event stream, returning the first schema failure."""
    for index, event in enumerate(events):
        result = validate_event(event, index=index)
        if not result.ok:
            return result
    return HAILValidationResult(ok=True)


def parse_jsonl_events(payload: str) -> tuple[HAILValidationResult, list[dict[str, Any]]]:
    """Parse and validate newline-delimited HAIL JSON text."""
    events: list[dict[str, Any]] = []
    for index, line in enumerate(payload.splitlines()):
        if not line.strip():
            continue
        try:
            event = json.loads(
                line,
                object_pairs_hook=object_pairs_no_duplicates,
                parse_constant=reject_non_finite_json_number,
            )
        except json.JSONDecodeError as exc:
            return (
                HAILValidationResult(
                    ok=False,
                    error_code=HAIL_JSON_INVALID,
                    validation_stage="json_parse",
                    message=str(exc),
                    index=index,
                ),
                events,
            )
        except DuplicateJSONKeyError as exc:
            return (
                HAILValidationResult(
                    ok=False,
                    error_code=HAIL_JSON_INVALID,
                    validation_stage="json_parse",
                    message=str(exc),
                    index=index,
                ),
                events,
            )
        except NonFiniteJSONNumberError as exc:
            return (
                HAILValidationResult(
                    ok=False,
                    error_code=HAIL_JSON_INVALID,
                    validation_stage="json_parse",
                    message=str(exc),
                    index=index,
                ),
                events,
            )
        if not isinstance(event, dict):
            return (
                HAILValidationResult(
                    ok=False,
                    error_code=HAIL_SCHEMA_INVALID,
                    validation_stage=HAIL_VALIDATION_STAGE,
                    message="HAIL JSONL records must be objects",
                    index=index,
                ),
                events,
            )
        events.append(event)
    return validate_events(events), events


def validate_jsonl(payload: str) -> HAILValidationResult:
    """Validate newline-delimited HAIL JSON text."""
    result, _ = parse_jsonl_events(payload)
    return result


def normalize_legacy_event(event: dict[str, Any]) -> dict[str, Any]:
    """Normalize one known legacy HAIL event into the v1 field shape."""
    normalized = dict(event)

    if normalized.get("kind") == "LCP_ATTEMPT":
        normalized["kind"] = "ECRP_ATTEMPT"

    if normalized.get("kind") == "ECRP_ATTEMPT":
        if "strategy" not in normalized and "lcp_id" in normalized:
            normalized["strategy"] = normalized.pop("lcp_id")
        else:
            normalized.pop("lcp_id", None)
        if normalized.get("outcome") == "RECOVERED":
            normalized["outcome"] = "SUCCESS"

    if normalized.get("kind") == "RUNTIME_STATE_SNAPSHOT":
        if "rimgb_hash" not in normalized and "rsb_hash" in normalized:
            normalized["rimgb_hash"] = normalized.pop("rsb_hash")
        else:
            normalized.pop("rsb_hash", None)

        if "state_fields" not in normalized and "fields" in normalized:
            normalized["state_fields"] = normalized.pop("fields")
        else:
            normalized.pop("fields", None)

        if "validity_window" not in normalized:
            start_t = normalized.pop("valid_from_t", None)
            end_t = normalized.pop("valid_to_t", None)
            if start_t is not None or end_t is not None:
                normalized["validity_window"] = {
                    "start_t": start_t,
                    "end_t": end_t,
                }
        else:
            normalized.pop("valid_from_t", None)
            normalized.pop("valid_to_t", None)

        normalized.pop("sampling", None)

    if normalized.get("kind") == "REPLAN_DECISION":
        if "inputs_ref" not in normalized and "inputs" in normalized:
            inputs = dict(normalized.pop("inputs"))
            if "simgb_hash" not in inputs and "dsb_hash" in inputs:
                inputs["simgb_hash"] = inputs.pop("dsb_hash")
            if "rimgb_hash" not in inputs and "rsb_hash" in inputs:
                inputs["rimgb_hash"] = inputs.pop("rsb_hash")
            inputs.pop("last_obs_t", None)
            normalized["inputs_ref"] = inputs

    return normalized


def normalize_legacy_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize known legacy HAIL events into v1 shape."""
    return [normalize_legacy_event(event) for event in events]

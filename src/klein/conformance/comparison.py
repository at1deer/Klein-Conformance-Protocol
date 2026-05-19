"""Conformance comparison, digest details, and negative evidence assertions."""

from __future__ import annotations

from typing import Any

from klein.common.hashing import hash_json_artifact, raw_file_sha256
from klein.conformance.errors import VECTOR_EVIDENCE_ASSERTION_FAILED
from klein.conformance.models import (
    CompareMode,
    ConformanceResult,
    ConformanceVector,
    ExecutionResult,
    Outcome,
)
from klein.hail.canonical import (
    canonicalize_events as hail_canonicalize_events,
)
from klein.hail.canonical import (
    compute_digest as hail_compute_digest,
)
from klein.hail.canonical import event_sort_key, hash_hail_jsonl
from klein.hail.canonical import (
    normalize_run_metadata as hail_normalize_run_metadata,
)
from klein.hail.chain import verify_hail_chain
from klein.hail.validation import parse_jsonl_events


def get_sort_key(event: dict[str, Any]) -> tuple:
    """
    Get sort key for EXACT_JSONL ordering.

    Sort order: (t, kind, tie_breaker)
    """
    return event_sort_key(event)


def canonicalize_events(events: list[dict[str, Any]]) -> list[str]:
    """
    Canonicalize events per klein.canon.jsonl.v1.

    Returns list of canonical JSON strings.
    """
    return hail_canonicalize_events(events)


def compute_digest(events: list[dict[str, Any]]) -> str:
    """Compute SHA256 digest of canonicalized events."""
    return hail_compute_digest(events)


# =============================================================================
# Comparison Functions
# =============================================================================


def compare_exact_jsonl(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> tuple[bool, str]:
    """
    EXACT_JSONL comparison mode.

    Events must match byte-for-byte after canonicalization.
    """
    actual_canon = canonicalize_events(actual)
    expected_canon = canonicalize_events(expected)

    if len(actual_canon) != len(expected_canon):
        return False, f"Event count mismatch: {len(actual_canon)} vs {len(expected_canon)}"

    for i, (a, e) in enumerate(zip(actual_canon, expected_canon, strict=True)):
        if a != e:
            return False, f"Mismatch at event {i}: {a[:100]}... vs {e[:100]}..."

    return True, "EXACT_JSONL match"


def compare_set(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
) -> tuple[bool, str]:
    """
    SET comparison mode.

    Events must match as unordered sets (order-independent).
    """
    actual_set = set(canonicalize_events(actual))
    expected_set = set(canonicalize_events(expected))

    if actual_set == expected_set:
        return True, "SET match"

    missing = expected_set - actual_set
    extra = actual_set - expected_set

    msg_parts = []
    if missing:
        msg_parts.append(f"Missing {len(missing)} events")
    if extra:
        msg_parts.append(f"Extra {len(extra)} events")

    return False, "; ".join(msg_parts)


def compare_envelope(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    tolerances: dict[str, float] | None = None,
) -> tuple[bool, str]:
    """
    ENVELOPE comparison mode.

    Numeric values compared within declared tolerances.
    """
    tolerances = tolerances or {}

    actual_sorted = sorted(actual, key=get_sort_key)
    expected_sorted = sorted(expected, key=get_sort_key)

    if len(actual_sorted) != len(expected_sorted):
        return False, f"Event count mismatch: {len(actual_sorted)} vs {len(expected_sorted)}"

    for i, (a, e) in enumerate(zip(actual_sorted, expected_sorted, strict=True)):
        # Check kind matches
        if a.get("kind") != e.get("kind"):
            return False, f"Kind mismatch at {i}: {a.get('kind')} vs {e.get('kind')}"

        # Check tick within tolerance
        t_tol = tolerances.get("t", 0)
        if abs(a.get("t", 0) - e.get("t", 0)) > t_tol:
            return (
                False,
                f"Tick mismatch at {i}: {a.get('t')} vs {e.get('t')} outside tolerance {t_tol}",
            )

    return True, "ENVELOPE match"


def envelope_details(
    actual: list[dict[str, Any]],
    expected: list[dict[str, Any]],
    tolerances: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Return alpha envelope comparison diagnostics."""
    tolerances = tolerances or {}
    actual_sorted = sorted(actual, key=get_sort_key)
    expected_sorted = sorted(expected, key=get_sort_key)
    margins: list[dict[str, Any]] = []
    reason = "envelope_match"
    if len(actual_sorted) != len(expected_sorted):
        reason = "event_count_mismatch"
    for index, (actual_event, expected_event) in enumerate(
        zip(actual_sorted, expected_sorted, strict=False)
    ):
        event_reason = "within_tolerance"
        if actual_event.get("kind") != expected_event.get("kind"):
            event_reason = "kind_mismatch"
            reason = reason if reason != "envelope_match" else event_reason
        actual_t = actual_event.get("t", 0)
        expected_t = expected_event.get("t", 0)
        tick_delta = abs(actual_t - expected_t)
        within = tick_delta <= tolerances.get("t", 0)
        if event_reason == "within_tolerance" and not within:
            event_reason = "tick_tolerance_exceeded"
            reason = reason if reason != "envelope_match" else event_reason
        margins.append(
            {
                "event_index": index,
                "kind": actual_event.get("kind"),
                "expected_kind": expected_event.get("kind"),
                "dimension": "t",
                "actual": actual_t,
                "expected": expected_t,
                "delta": tick_delta,
                "tolerance": tolerances.get("t", 0),
                "margin": tolerances.get("t", 0) - tick_delta,
                "within": within,
                "reason": event_reason,
            }
        )
    return {
        "tolerances": tolerances,
        "actual_event_count": len(actual_sorted),
        "expected_event_count": len(expected_sorted),
        "margins": margins,
        "reason": reason,
        "alpha_scope": "minimal event count, kind, and tick tolerance comparison",
    }


# =============================================================================


def extract_error_code(events: list[dict[str, Any]]) -> str | None:
    """Extract the first explicit error code from a HAIL stream."""
    for event in events:
        if event.get("kind") == "DEVICE_EVENT" and event.get("level") == "ERROR":
            code = event.get("code")
            return str(code) if code is not None else None
    for event in events:
        code = event.get("code")
        if isinstance(code, str) and code.startswith("E_"):
            return code
    return None


def classify_actual_result(exec_result: ExecutionResult, error_code: str | None) -> str:
    """Classify backend execution into the conformance result vocabulary."""
    if error_code or not exec_result.success:
        return "FAIL"
    return "PASS"


def make_conformance_result(
    vector: ConformanceVector,
    outcome: Outcome,
    message: str,
    *,
    duration_ms: float = 0.0,
    actual_result: str | None = None,
    actual_error_code: str | None = None,
    validation_stage: str | None = None,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> ConformanceResult:
    """Build a result with both legacy and v1 result fields populated."""
    return ConformanceResult(
        vector_id=vector.id,
        vector_name=vector.name,
        outcome=outcome,
        message=message,
        expected_result=vector.expected_result,
        actual_result=actual_result,
        expected_error_code=vector.expected_error_code,
        actual_error_code=actual_error_code,
        validation_stage=validation_stage,
        reason=reason,
        duration_ms=duration_ms,
        expected_error=vector.expected_error_code,
        actual_error=actual_error_code,
        details=details or {},
    )


def comparison_inputs(
    vector: ConformanceVector,
    actual_events: list[dict[str, Any]],
    expected_events: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Apply vector-declared comparison normalization."""
    if not vector.normalize_run_metadata:
        return actual_events, expected_events
    return (
        hail_normalize_run_metadata(actual_events),
        hail_normalize_run_metadata(expected_events),
    )


def comparison_details(
    vector: ConformanceVector,
    actual_events: list[dict[str, Any]],
    expected_events: list[dict[str, Any]],
    compare_mode: CompareMode,
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build comparison diagnostics recorded in conformance results."""
    actual_for_digest, expected_for_digest = comparison_inputs(
        vector,
        actual_events,
        expected_events,
    )
    details: dict[str, Any] = {
        "comparison_mode": compare_mode.value,
        "normalized_run_metadata": vector.normalize_run_metadata,
        "actual_event_count": len(actual_events),
        "expected_event_count": len(expected_events),
        "digest_actual": compute_digest(actual_for_digest) if actual_for_digest else None,
        "digest_expected": compute_digest(expected_for_digest) if expected_for_digest else None,
        "input_type": vector.input_type,
        "input_path": str(vector.input_path) if vector.input_path else None,
        "signed_conformance": vector.signed_conformance,
        "bundle_conformance": vector.bundle_conformance,
        "run_bundle_present": vector.run_bundle_path is not None,
        "run_bundle_verified": None,
        "run_bundle_format": None,
        "run_bundle_error_code": None,
        "run_bundle_signed_conformance_status": None,
        "run_manifest_present": vector.run_manifest_path is not None,
        "run_manifest_verified": None,
        "run_manifest_signature_status": None,
        "run_manifest_trust_status": None,
        "run_manifest_key_id": None,
        "run_manifest_signature_algorithm": None,
        "run_manifest_error_code": None,
    }
    details.update(input_artifact_binding_details(vector))
    details.update(lifecycle_binding_details(actual_events))
    if extra:
        details.update(extra)
    if vector.schema_version != "v1":
        details.setdefault("classification", "unmigrated_legacy_semantics")
    return details


def lifecycle_binding_details(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Return report diagnostics derived from RUN_START/RUN_END events."""
    run_start = next((event for event in events if event.get("kind") == "RUN_START"), None)
    run_end = next((event for event in events if event.get("kind") == "RUN_END"), None)
    details: dict[str, Any] = {
        "run_start_present": run_start is not None,
        "run_end_present": run_end is not None,
        "lifecycle_bound": False,
        "preclose_hail_digest": None,
        "preclose_hail_digest_computed": None,
        "preclose_hail_digest_matches": None,
        "hail_chain_algorithm": None,
        "preclose_hail_chain_digest": None,
        "run_end_preclose_hail_chain_digest": None,
        "hail_chain_matches_run_end": None,
        "event_count_chained": None,
        "hail_chain_canonical_order_ok": None,
    }
    if run_start is not None:
        details.update(
            {
                "run_start_artifact_hash": run_start.get("artifact_hash"),
                "run_start_artifact_canonicalization": run_start.get(
                    "artifact_canonicalization"
                ),
                "run_start_profile_id": run_start.get("profile_id"),
                "run_start_profile_version": run_start.get("profile_version"),
                "run_start_backend_id": run_start.get("backend_id"),
                "run_start_substrate_fingerprint": run_start.get("substrate_fingerprint"),
            }
        )
    if run_end is not None:
        preclose_events = [event for event in events if event is not run_end]
        computed = hash_hail_jsonl(preclose_events).ref if preclose_events else None
        declared = run_end.get("preclose_hail_digest")
        matches = computed == declared
        chain_verification = verify_hail_chain(events)
        chain_result = chain_verification.result
        details.update(
            {
                "preclose_hail_digest": declared,
                "preclose_hail_digest_computed": computed,
                "preclose_hail_digest_matches": matches,
                "hail_chain_algorithm": (
                    chain_result.chain_algorithm if chain_result is not None else None
                ),
                "preclose_hail_chain_digest": (
                    chain_result.terminal_chain_digest_ref if chain_result is not None else None
                ),
                "run_end_preclose_hail_chain_digest": run_end.get(
                    "preclose_hail_chain_digest"
                ),
                "hail_chain_matches_run_end": chain_verification.matches_run_end,
                "event_count_chained": (
                    chain_result.event_count_chained if chain_result is not None else None
                ),
                "hail_chain_canonical_order_ok": chain_verification.canonical_order_ok,
                "event_count_preclose": run_end.get("event_count_preclose"),
                "run_end_status": run_end.get("status"),
                "run_end_error_code": run_end.get("error_code"),
            }
        )
        details["lifecycle_bound"] = (
            run_start is not None
            and matches
            and chain_verification.matches_run_end is True
        )
    return details


def input_artifact_binding_details(vector: ConformanceVector) -> dict[str, Any]:
    """Return canonical/raw input artifact binding fields for v1 vectors."""
    path = vector.input_path
    if vector.schema_version != "v1" or path is None:
        return {}

    details: dict[str, Any] = {
        "input_artifact_hash": None,
        "input_artifact_hash_mode": None,
        "input_artifact_canonicalization": None,
        "input_raw_sha256": None,
    }
    if not path.exists():
        return details

    raw_hash = raw_file_sha256(path)
    details["input_raw_sha256"] = raw_hash.ref

    try:
        if vector.input_type == "hail_jsonl":
            validation, events = parse_jsonl_events(path.read_text(encoding="utf-8"))
            if not validation.ok:
                details["input_artifact_hash_error"] = validation.error_code
                details["input_artifact_hash_stage"] = validation.validation_stage
                return details
            artifact_hash = hash_hail_jsonl(events)
            details["input_artifact_hash"] = artifact_hash.ref
            details["input_artifact_hash_mode"] = "canonical_hail_jsonl"
            details["input_artifact_canonicalization"] = artifact_hash.canonicalization
            return details

        if vector.input_type in {"project", "container", "invalid_artifact"}:
            artifact_hash = hash_json_artifact(path)
            details["input_artifact_hash"] = artifact_hash.ref
            details["input_artifact_hash_mode"] = "canonical_json"
            details["input_artifact_canonicalization"] = artifact_hash.canonicalization
            return details
    except Exception as exc:
        details["input_artifact_hash_error"] = type(exc).__name__

    return details


def check_required_negative_evidence(
    vector: ConformanceVector,
    events: list[dict[str, Any]],
) -> tuple[bool, str, dict[str, Any]]:
    """Validate optional event evidence requirements for negative v1 vectors."""
    required_kinds = vector.metadata.get("required_event_kinds", [])
    required_codes = vector.metadata.get("required_event_codes", [])
    kinds = {event.get("kind") for event in events}
    codes = {event.get("code") for event in events if "code" in event}

    for kind in required_kinds:
        if kind not in kinds:
            return (
                False,
                f"Missing required event kind {kind}",
                {
                    "evidence_error_code": VECTOR_EVIDENCE_ASSERTION_FAILED,
                    "missing_kind": kind,
                },
            )
    for code in required_codes:
        if code not in codes:
            return (
                False,
                f"Missing required event code {code}",
                {
                    "evidence_error_code": VECTOR_EVIDENCE_ASSERTION_FAILED,
                    "missing_code": code,
                },
            )

    assertions = vector.metadata.get("evidence_assertions", [])
    if assertions:
        ok, msg, detail = check_evidence_assertions(assertions, events)
        if not ok:
            detail["evidence_error_code"] = VECTOR_EVIDENCE_ASSERTION_FAILED
            return False, msg, detail
    return True, "Required negative evidence present", {}


def check_evidence_assertions(
    assertions: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> tuple[bool, str, dict[str, Any]]:
    """Check ordered evidence assertions with exact field equality."""
    next_index = 0
    for assertion_index, assertion in enumerate(assertions):
        if not isinstance(assertion, dict):
            return (
                False,
                f"Evidence assertion {assertion_index} is not an object",
                {
                    "assertion_index": assertion_index,
                    "assertion": assertion,
                },
            )
        found_index = None
        for event_index in range(next_index, len(events)):
            if event_matches_assertion(events[event_index], assertion):
                found_index = event_index
                break
        if found_index is None:
            return (
                False,
                f"Evidence assertion {assertion_index} not observed",
                {
                    "assertion_index": assertion_index,
                    "assertion": assertion,
                },
            )
        next_index = found_index + 1
    return True, "Evidence assertions observed", {}


def event_matches_assertion(event: dict[str, Any], assertion: dict[str, Any]) -> bool:
    """Return True when an event satisfies an exact evidence assertion."""
    kind = assertion.get("kind")
    if kind is not None and event.get("kind") != kind:
        return False
    where = assertion.get("where", {})
    if not isinstance(where, dict):
        return False
    for path, expected in where.items():
        actual, exists = get_path(event, str(path))
        if not exists or actual != expected:
            return False
    return True


def get_path(payload: dict[str, Any], path: str) -> tuple[Any, bool]:
    """Resolve a dotted field path from a nested dict payload."""
    current: Any = payload
    for segment in path.split("."):
        if not isinstance(current, dict) or segment not in current:
            return None, False
        current = current[segment]
    return current, True

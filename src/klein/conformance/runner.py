"""Conformance vector runner."""

from __future__ import annotations

import time
from typing import Any

from klein.bundle import verify_run_bundle
from klein.conformance.backends import Backend
from klein.conformance.comparison import (
    check_required_negative_evidence,
    classify_actual_result,
    compare_envelope,
    compare_exact_jsonl,
    compare_set,
    comparison_details,
    comparison_inputs,
    envelope_details,
    extract_error_code,
    make_conformance_result,
)
from klein.conformance.errors import (
    HAIL_SCHEMA_INVALID,
    VECTOR_GOLDEN_MISSING,
    VECTOR_INPUT_MISSING,
)
from klein.conformance.models import CompareMode, ConformanceResult, ConformanceVector, Outcome
from klein.hail.validation import validate_events
from klein.verifier import verify_signed_conformance


def run_manifest_details(vector: ConformanceVector, events: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify an optional signed run manifest declared by a v1 vector."""
    details: dict[str, Any] = {
        "run_manifest_present": vector.run_manifest_path is not None,
        "run_manifest_verified": None,
        "run_manifest_signature_status": None,
        "run_manifest_trust_status": None,
        "run_manifest_key_id": None,
        "run_manifest_signature_algorithm": None,
        "run_manifest_error_code": None,
        "signed_conformance": vector.signed_conformance,
    }
    if vector.run_manifest_path is None:
        return details
    try:
        verification = verify_signed_conformance(
            manifest_path=vector.run_manifest_path,
            trust_policy_path=vector.trust_policy_path,
            artifact_path=vector.input_path,
            events=events,
        )
    except Exception as exc:  # noqa: BLE001 - conformance reports normalize manifest failures.
        details["run_manifest_verified"] = False
        details["run_manifest_error_code"] = getattr(exc, "error_code", "RUN_MANIFEST_INVALID")
        return details
    details["run_manifest_verified"] = verification.ok
    details["run_manifest_signature_status"] = (
        "valid" if verification.signature_status == "pass" else "invalid"
    )
    details["run_manifest_trust_status"] = (
        "trusted" if verification.trust_status == "pass" else "untrusted"
    )
    details["run_manifest_key_id"] = (
        verification.manifest_key_ids[0] if verification.manifest_key_ids else None
    )
    details["run_manifest_signature_algorithm"] = "Ed25519" if verification.manifest_key_ids else None
    details["run_manifest_error_code"] = (
        verification.errors[0]["error_code"] if verification.errors else None
    )
    details["signed_conformance_overall_status"] = verification.overall_status
    return details


def run_bundle_details(vector: ConformanceVector) -> dict[str, Any]:
    """Verify an optional KCP Run Bundle v1 declared by a v1 vector."""
    details: dict[str, Any] = {
        "bundle_conformance": vector.bundle_conformance,
        "run_bundle_present": vector.run_bundle_path is not None,
        "run_bundle_verified": None,
        "run_bundle_format": None,
        "run_bundle_error_code": None,
        "run_bundle_signed_conformance_status": None,
    }
    if vector.run_bundle_path is None:
        return details
    verification = verify_run_bundle(vector.run_bundle_path)
    details["run_bundle_verified"] = verification.ok
    details["run_bundle_format"] = verification.bundle_format
    details["run_bundle_signed_conformance_status"] = verification.signed_conformance_status
    details["run_bundle_error_code"] = verification.errors[0]["error_code"] if verification.errors else None
    return details


def run_vector(
    vector: ConformanceVector,
    backend: Backend,
    compare_mode: CompareMode = CompareMode.EXACT_JSONL,
) -> ConformanceResult:
    """
    Run a single test vector.

    Args:
        vector: The test vector to run
        backend: Backend to execute against
        compare_mode: Comparison mode to use

    Returns:
        ConformanceResult with outcome
    """
    start = time.perf_counter()

    if (
        vector.schema_version == "v1"
        and not vector.is_negative
        and (not vector.input_type or vector.input_path is None or not vector.input_path.exists())
    ):
        return make_conformance_result(
            vector,
            Outcome.FAIL,
            "v1 vector is missing its declared input artifact",
            duration_ms=(time.perf_counter() - start) * 1000,
            actual_result="FAIL",
            actual_error_code=VECTOR_INPUT_MISSING,
            validation_stage="vector_input",
            reason="v1_input_missing",
            details=comparison_details(
                vector,
                [],
                vector.golden_observables,
                vector.comparison_mode or compare_mode,
            ),
        )

    if vector.schema_version == "v1":
        if vector.golden_error_code:
            return make_conformance_result(
                vector,
                Outcome.FAIL,
                vector.golden_error_message or "v1 golden HAIL failed validation",
                duration_ms=(time.perf_counter() - start) * 1000,
                actual_result="FAIL",
                actual_error_code=vector.golden_error_code,
                validation_stage=vector.golden_validation_stage,
                reason="v1_golden_invalid",
                details={
                    "golden_path": str(vector.golden_path) if vector.golden_path else None,
                    "line_index": vector.golden_error_index,
                    "input_type": vector.input_type,
                    "input_path": str(vector.input_path) if vector.input_path else None,
                },
            )
        if not vector.is_negative and not vector.golden_observables:
            return make_conformance_result(
                vector,
                Outcome.FAIL,
                "v1 positive vector is missing golden observables",
                duration_ms=(time.perf_counter() - start) * 1000,
                actual_result="FAIL",
                actual_error_code=VECTOR_GOLDEN_MISSING,
                validation_stage="golden_schema",
                reason="v1_golden_missing",
                details={
                    "golden_path": str(vector.golden_path) if vector.golden_path else None,
                    "input_type": vector.input_type,
                    "input_path": str(vector.input_path) if vector.input_path else None,
                },
            )

    # Check capabilities
    if vector.required_capabilities:
        ok, msg = backend.check_capabilities(vector.required_capabilities)
        if not ok:
            return make_conformance_result(vector, Outcome.SKIP, msg, actual_result="SKIP")

    effective_compare_mode = vector.comparison_mode or compare_mode

    # Legacy vectors may still have no executable content. v1 vectors must execute
    # through the backend so missing declared inputs become VECTOR_INPUT_MISSING.
    if vector.schema_version != "v1" and not vector.container and not vector.loose_path:
        return make_conformance_result(
            vector,
            Outcome.SKIP,
            "No executable content found",
            actual_result="SKIP",
        )

    try:
        # Execute
        exec_result = backend.execute(vector)
        actual_events = exec_result.events
        actual_error_code = exec_result.error_code or extract_error_code(actual_events)
        validation_stage = exec_result.validation_stage

        if vector.schema_version == "v1":
            validation = validate_events(actual_events)
            if not validation.ok:
                actual_error_code = actual_error_code or validation.error_code
                validation_stage = validation_stage or validation.validation_stage

        actual_result = classify_actual_result(exec_result, actual_error_code)
        base_details = comparison_details(
            vector,
            actual_events,
            vector.golden_observables,
            effective_compare_mode,
            extra=exec_result.details,
        )
        signed_details = run_manifest_details(vector, actual_events)
        bundle_details = run_bundle_details(vector)
        base_details.update(signed_details)
        base_details.update(bundle_details)
        if vector.signed_conformance and signed_details["run_manifest_verified"] is not True:
            actual_result = "FAIL"
            actual_error_code = signed_details["run_manifest_error_code"] or "RUN_MANIFEST_INVALID"
            validation_stage = validation_stage or "signed_conformance"
        if vector.bundle_conformance and bundle_details["run_bundle_verified"] is not True:
            actual_result = "FAIL"
            actual_error_code = bundle_details["run_bundle_error_code"] or "RUN_BUNDLE_INVALID"
            validation_stage = validation_stage or "bundle_conformance"

        if vector.is_negative:
            expected_code = vector.expected_error_code
            if not expected_code:
                return make_conformance_result(
                    vector,
                    Outcome.FAIL,
                    "Negative vector is missing expected_error_code",
                    duration_ms=exec_result.duration_ms,
                    actual_result=actual_result,
                    actual_error_code=actual_error_code,
                    validation_stage=validation_stage,
                    reason="missing_expected_error_code",
                    details=base_details,
                )

            if actual_result != "FAIL":
                return make_conformance_result(
                    vector,
                    Outcome.FAIL,
                    f"Expected failure {expected_code}, but execution passed",
                    duration_ms=exec_result.duration_ms,
                    actual_result=actual_result,
                    actual_error_code=actual_error_code,
                    validation_stage=validation_stage,
                    reason="negative_unexpected_pass",
                    details=base_details,
                )

            if actual_error_code != expected_code:
                return make_conformance_result(
                    vector,
                    Outcome.FAIL,
                    f"Expected error {expected_code}, got {actual_error_code or 'None'}",
                    duration_ms=exec_result.duration_ms,
                    actual_result=actual_result,
                    actual_error_code=actual_error_code,
                    validation_stage=validation_stage,
                    reason="negative_error_mismatch",
                    details=base_details,
                )

            if (
                vector.expected_validation_stage
                and validation_stage != vector.expected_validation_stage
            ):
                return make_conformance_result(
                    vector,
                    Outcome.FAIL,
                    f"Expected validation stage {vector.expected_validation_stage}, got {validation_stage}",
                    duration_ms=exec_result.duration_ms,
                    actual_result=actual_result,
                    actual_error_code=actual_error_code,
                    validation_stage=validation_stage,
                    reason="negative_stage_mismatch",
                    details=base_details,
                )

            evidence_ok, evidence_msg, evidence_detail = check_required_negative_evidence(
                vector, actual_events
            )
            if not evidence_ok:
                evidence_details = dict(base_details)
                evidence_details.update(evidence_detail)
                return make_conformance_result(
                    vector,
                    Outcome.FAIL,
                    evidence_msg,
                    duration_ms=exec_result.duration_ms,
                    actual_result=actual_result,
                    actual_error_code=actual_error_code,
                    validation_stage=validation_stage,
                    reason="negative_evidence_assertion_failed",
                    details=evidence_details,
                )

            return make_conformance_result(
                vector,
                Outcome.PASS,
                f"Observed expected failure: {expected_code}",
                duration_ms=exec_result.duration_ms,
                actual_result=actual_result,
                actual_error_code=actual_error_code,
                validation_stage=validation_stage,
                details=base_details,
            )

        if actual_error_code == HAIL_SCHEMA_INVALID:
            return make_conformance_result(
                vector,
                Outcome.FAIL,
                "Actual HAIL stream failed v1 schema validation",
                duration_ms=exec_result.duration_ms,
                actual_result="FAIL",
                actual_error_code=actual_error_code,
                validation_stage=validation_stage,
                reason="hail_schema_invalid",
                details=base_details,
            )

        if actual_result == "FAIL":
            return make_conformance_result(
                vector,
                Outcome.FAIL,
                f"Execution failed: {actual_error_code or exec_result.error_message or 'unknown error'}",
                duration_ms=exec_result.duration_ms,
                actual_result=actual_result,
                actual_error_code=actual_error_code or "EXECUTION_FAILED",
                validation_stage=validation_stage,
                reason="execution_failed",
                details=base_details,
            )

        # Get expected
        expected_events = vector.golden_observables

        if not expected_events:
            if vector.schema_version == "v1":
                return make_conformance_result(
                    vector,
                    Outcome.FAIL,
                    "v1 vector is missing golden observables",
                    duration_ms=exec_result.duration_ms,
                    actual_result="FAIL",
                    actual_error_code=VECTOR_GOLDEN_MISSING,
                    validation_stage=validation_stage,
                    reason="v1_golden_missing",
                    details=base_details,
                )
            # No golden to compare against
            if exec_result.success and actual_events:
                return make_conformance_result(
                    vector,
                    Outcome.PASS,
                    f"Execution succeeded ({len(actual_events)} events)",
                    duration_ms=exec_result.duration_ms,
                    actual_result=actual_result,
                    actual_error_code=actual_error_code,
                    validation_stage=validation_stage,
                    details=base_details,
                )
            return make_conformance_result(
                vector,
                Outcome.SKIP,
                "No golden observables to compare",
                duration_ms=exec_result.duration_ms,
                actual_result=actual_result,
                actual_error_code=actual_error_code,
                validation_stage=validation_stage,
                details=base_details,
            )

        actual_compare, expected_compare = comparison_inputs(vector, actual_events, expected_events)

        # Compare based on mode
        comparison_extra: dict[str, Any] = {}
        if effective_compare_mode == CompareMode.EXACT_JSONL:
            ok, msg = compare_exact_jsonl(actual_compare, expected_compare)
        elif effective_compare_mode == CompareMode.SET:
            ok, msg = compare_set(actual_compare, expected_compare)
        else:
            tolerances = vector.expected.get("envelope") or vector.expected.get("tolerances")
            ok, msg = compare_envelope(actual_compare, expected_compare, tolerances=tolerances)
            comparison_extra["envelope"] = envelope_details(
                actual_compare,
                expected_compare,
                tolerances=tolerances,
            )
        final_details = comparison_details(
            vector,
            actual_events,
            expected_events,
            effective_compare_mode,
            extra={**exec_result.details, **comparison_extra},
        )
        final_details.update(signed_details)
        final_details.update(bundle_details)

        outcome = Outcome.PASS if ok else Outcome.FAIL
        if not ok:
            actual_result = "FAIL"
            actual_error_code = actual_error_code or "OUTPUT_MISMATCH"
        elif vector.run_manifest_path is not None and final_details["run_manifest_verified"] is not True:
            outcome = Outcome.FAIL
            actual_result = "FAIL"
            actual_error_code = final_details["run_manifest_error_code"] or "RUN_MANIFEST_INVALID"
        elif vector.signed_conformance and final_details["run_manifest_trust_status"] != "trusted":
            outcome = Outcome.FAIL
            actual_result = "FAIL"
            actual_error_code = "BACKEND_IDENTITY_UNTRUSTED"
        elif vector.bundle_conformance and final_details["run_bundle_verified"] is not True:
            outcome = Outcome.FAIL
            actual_result = "FAIL"
            actual_error_code = final_details["run_bundle_error_code"] or "RUN_BUNDLE_INVALID"

        return make_conformance_result(
            vector,
            outcome,
            msg,
            duration_ms=exec_result.duration_ms,
            actual_result=actual_result,
            actual_error_code=actual_error_code,
            validation_stage=validation_stage,
            details=final_details,
        )

    except Exception as e:
        return make_conformance_result(
            vector,
            Outcome.ERROR,
            str(e),
            duration_ms=(time.perf_counter() - start) * 1000,
            actual_result="ERROR",
            actual_error_code="HARNESS_EXCEPTION",
        )


# =============================================================================

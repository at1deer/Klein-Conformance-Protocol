"""Runbook and execution trace helpers."""

from __future__ import annotations

from klein.execution.ecrp import (
    ECRPError,
    ECRPValidationResult,
    canonical_ecrp_policy_hash,
    default_ecrp_policy_for_mode,
    load_ecrp_policy,
    validate_ecrp_attempt_sequence,
    validate_ecrp_policy,
    validate_trace_recovery_contract,
)
from klein.execution.observation import (
    ObservationError,
    ObservationValidationResult,
    build_dmf_simulated_observation,
    build_dmf_simulated_observations_from_events,
    canonical_observation_hash,
    compare_observation_to_runbook,
    compare_observation_to_trace,
    default_observation_policy,
    load_observation_json,
    validate_dmf_observation_state,
    validate_observation_contract,
    validate_observation_policy,
    validate_observation_snapshot,
)
from klein.execution.runbook import build_runbook_from_artifact
from klein.execution.trace import (
    build_trace_from_execution_result,
    build_trace_from_hail_events,
    build_trace_from_runbook,
)
from klein.execution.validation import (
    ExecutionArtifactError,
    TraceComparisonResult,
    canonical_runbook_hash,
    canonical_trace_hash,
    compare_trace_to_runbook,
    validate_execution_trace,
    validate_runbook,
)

__all__ = [
    "ExecutionArtifactError",
    "ECRPError",
    "ECRPValidationResult",
    "ObservationError",
    "ObservationValidationResult",
    "TraceComparisonResult",
    "build_dmf_simulated_observation",
    "build_dmf_simulated_observations_from_events",
    "build_runbook_from_artifact",
    "build_trace_from_execution_result",
    "build_trace_from_hail_events",
    "build_trace_from_runbook",
    "canonical_runbook_hash",
    "canonical_ecrp_policy_hash",
    "canonical_observation_hash",
    "canonical_trace_hash",
    "compare_observation_to_runbook",
    "compare_observation_to_trace",
    "compare_trace_to_runbook",
    "default_observation_policy",
    "default_ecrp_policy_for_mode",
    "load_observation_json",
    "load_ecrp_policy",
    "validate_dmf_observation_state",
    "validate_ecrp_attempt_sequence",
    "validate_execution_trace",
    "validate_ecrp_policy",
    "validate_observation_contract",
    "validate_observation_policy",
    "validate_observation_snapshot",
    "validate_runbook",
    "validate_trace_recovery_contract",
]

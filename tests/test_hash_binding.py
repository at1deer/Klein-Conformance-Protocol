from __future__ import annotations

import math
from pathlib import Path

import pytest

from klein.common.hashing import canonical_json_sha256_ref, hash_json_artifact
from klein.conformance.backends import FullSimulatorBackend
from klein.conformance.runner import run_vector
from klein.conformance.suite import discover_vectors
from klein.hail.canonical import hash_hail_jsonl
from klein.hail.chain import compute_hail_chain, verify_hail_chain
from klein.hail.validation import validate_events
from klein.profiles.dmf import hash_substrate_fingerprint, substrate_fingerprint_details
from klein.sim.virtual_substrate import VirtualSubstrate
from klein.substrate.api import CapabilityProfile, FrequencyRange, TimingProfile, VoltageRange
from klein.tools.hash_artifact import main as hash_artifact_main


def test_canonical_json_hash_uses_jcs_numeric_and_key_rules() -> None:
    assert canonical_json_sha256_ref({"a": 1.0}) == canonical_json_sha256_ref({"a": 1})
    assert canonical_json_sha256_ref({"b": 2, "a": 1}) == canonical_json_sha256_ref(
        {"a": 1, "b": 2}
    )


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf, 9_007_199_254_740_992])
def test_canonical_json_hash_rejects_non_ijson_values(value: float | int) -> None:
    with pytest.raises(ValueError):
        canonical_json_sha256_ref({"value": value})


def test_hash_json_artifact_rejects_duplicate_names(tmp_path: Path) -> None:
    artifact = tmp_path / "dup.klein"
    artifact.write_text('{"a":1,"a":2}', encoding="utf-8")

    with pytest.raises(ValueError, match="duplicate JSON object name"):
        hash_json_artifact(artifact)


def test_canonical_json_hash_rejects_non_string_object_keys() -> None:
    with pytest.raises(TypeError, match="object keys must be strings"):
        canonical_json_sha256_ref({1: "not-json"})


def test_hash_json_artifact_changes_when_input_changes(tmp_path: Path) -> None:
    first = tmp_path / "first.klein"
    second = tmp_path / "second.klein"
    first.write_text('{"meta":{"version":"1.0"},"nodes":[],"edges":[]}', encoding="utf-8")
    second.write_text('{"meta":{"version":"1.1"},"nodes":[],"edges":[]}', encoding="utf-8")

    assert hash_json_artifact(first).ref != hash_json_artifact(second).ref


def test_conformance_report_binds_positive_input_artifact_and_substrate() -> None:
    vector = discover_vectors(
        vector_ids=["002"],
        suite_dir=Path("tests/vectors/v1"),
    )[0]

    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome.value == "PASS"
    assert result.details["input_artifact_hash"].startswith("sha256:")
    assert result.details["input_artifact_canonicalization"] == "klein.canon.json.v1"
    assert result.details["input_raw_sha256"].startswith("sha256:")
    assert result.details["profile_id"] == "dmf"
    assert result.details["backend_id"] == "full_simulator"
    assert result.details["substrate_capabilities_hash"].startswith("sha256:")
    assert result.details["substrate_topology_hash"].startswith("sha256:")
    assert result.details["substrate_fingerprint"].startswith("sha256:")
    assert result.details["lifecycle_bound"] is True
    assert result.details["run_start_artifact_hash"] == result.details["input_artifact_hash"]
    assert result.details["run_start_profile_id"] == result.details["profile_id"]
    assert result.details["run_start_backend_id"] == result.details["backend_id"]
    assert result.details["run_start_substrate_fingerprint"] == result.details["substrate_fingerprint"]
    assert result.details["preclose_hail_digest_matches"] is True
    assert result.details["hail_chain_algorithm"] == "klein.hail.chain.v1"
    assert result.details["hail_chain_matches_run_end"] is True
    assert result.details["hail_chain_canonical_order_ok"] is True
    assert result.details["preclose_hail_chain_digest"].startswith("sha256:")
    assert result.details["preclose_hail_chain_digest"] == result.details[
        "run_end_preclose_hail_chain_digest"
    ]
    execution = FullSimulatorBackend().execute(vector)
    assert result.details["digest_actual"] == hash_hail_jsonl(execution.events).digest_hex


def test_execution_vectors_emit_valid_lifecycle_binding_events() -> None:
    vector = discover_vectors(
        vector_ids=["002"],
        suite_dir=Path("tests/vectors/v1"),
    )[0]

    execution = FullSimulatorBackend().execute(vector)
    assert validate_events(execution.events).ok
    run_start = next(event for event in execution.events if event["kind"] == "RUN_START")
    run_end = next(event for event in execution.events if event["kind"] == "RUN_END")

    assert run_start["artifact_hash"] == execution.details["input_artifact_hash"]
    assert run_start["profile_id"] == execution.details["profile_id"]
    assert run_start["substrate_fingerprint"] == execution.details["substrate_fingerprint"]
    preclose_events = [event for event in execution.events if event is not run_end]
    assert run_end["preclose_hail_digest"] == hash_hail_jsonl(preclose_events).ref
    assert run_end["preclose_hail_chain_digest"] == compute_hail_chain(
        preclose_events
    ).terminal_chain_digest_ref
    assert run_end["preclose_hail_chain_algorithm"] == "klein.hail.chain.v1"
    assert run_end["event_count_preclose"] == len(preclose_events)
    assert verify_hail_chain(execution.events).matches_run_end is True


def test_direct_hail_vectors_are_not_wrapped_with_lifecycle_events() -> None:
    vector = discover_vectors(
        vector_ids=["004"],
        suite_dir=Path("tests/vectors/v1"),
    )[0]

    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome.value == "PASS"
    assert result.details["run_start_present"] is False
    assert result.details["run_end_present"] is False
    assert result.details["lifecycle_bound"] is False
    assert result.details["hail_chain_matches_run_end"] is None


def test_malformed_input_records_raw_hash_without_canonical_artifact_hash() -> None:
    vector = discover_vectors(
        vector_ids=["N005"],
        suite_dir=Path("tests/vectors/v1"),
    )[0]

    result = run_vector(vector, FullSimulatorBackend())

    assert result.outcome.value == "PASS"
    assert result.details["input_raw_sha256"].startswith("sha256:")
    assert result.details["input_artifact_hash"] is None
    assert result.details["input_artifact_hash_error"] == "JSONDecodeError"


def test_substrate_fingerprint_changes_with_declared_capabilities() -> None:
    substrate = VirtualSubstrate(max_channels=16, grid_width=4, grid_height=4)
    substrate.connect("virtual://test")
    base = substrate_fingerprint_details(substrate)

    limited_capabilities = CapabilityProfile(
        device_vendor="klein-sim",
        device_model="VirtualSubstrate",
        firmware="1.0.0",
        max_channels=16,
        addressing=substrate.get_capabilities().addressing,
        supports_groups=True,
        waveforms=substrate.get_capabilities().waveforms,
        voltage_range=VoltageRange(v_min=0.0, v_max=100.0),
        ac_frequency_range=FrequencyRange(hz_min=1.0, hz_max=50_000.0),
        timing=TimingProfile(min_frame_ms=5, typical_jitter_ms=1, max_schedule_horizon_ms=5000),
        sensing=substrate.get_capabilities().sensing,
        safety_estop=True,
        safety_overcurrent_protection=True,
    )
    changed = VirtualSubstrate(
        max_channels=16,
        grid_width=4,
        grid_height=4,
        capabilities=limited_capabilities,
    )
    changed.connect("virtual://test")

    assert base["substrate_fingerprint"] != substrate_fingerprint_details(changed)[
        "substrate_fingerprint"
    ]


def test_substrate_fingerprint_changes_with_declared_topology() -> None:
    first = VirtualSubstrate(max_channels=16, grid_width=4, grid_height=4)
    first.connect("virtual://test")
    second = VirtualSubstrate(max_channels=16, grid_width=8, grid_height=2)
    second.connect("virtual://test")

    assert hash_substrate_fingerprint(first.get_capabilities(), first.get_topology()).ref != (
        hash_substrate_fingerprint(second.get_capabilities(), second.get_topology()).ref
    )


def test_hash_artifact_cli_hashes_json_and_hail(capsys: pytest.CaptureFixture[str]) -> None:
    assert hash_artifact_main(["tests/vectors/v1/core/001_hard_minimal_project/input/project.klein"]) == 0
    json_hash = capsys.readouterr().out.strip()
    assert json_hash.startswith("sha256:")

    assert hash_artifact_main(["tests/fixtures/canonicalization/hail_events_unsorted.jsonl"]) == 0
    hail_hash = capsys.readouterr().out.strip()
    assert hail_hash == "sha256:e85eedb37e0e13857cad58d9708f1374f9fcf415bb30fa6fa99a4c4d086d3a87"

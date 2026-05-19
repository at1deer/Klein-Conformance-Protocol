from __future__ import annotations

import math

import pytest

from klein.hail.canonical import (
    canonicalize_events,
    compute_digest,
    dump_canonical,
    normalize_run_metadata,
)
from klein.hail.validation import (
    HAIL_JSON_INVALID,
    HAIL_SCHEMA_INVALID,
    normalize_legacy_event,
    parse_jsonl_events,
    validate_event,
    validate_events,
)


def test_validate_device_event_v1() -> None:
    result = validate_event(
        {
            "kind": "DEVICE_EVENT",
            "t": 0,
            "timebase": "DEVICE_TICKS",
            "run_id": "R1",
            "code": "INIT",
            "level": "INFO",
            "message": "Run initialized",
        }
    )

    assert result.ok


def test_validate_ecrp_no_change_v1() -> None:
    result = validate_event(
        {
            "kind": "ECRP_ATTEMPT",
            "t": 5,
            "timebase": "DEVICE_TICKS",
            "run_id": "R1",
            "attempt_index": 1,
            "strategy": "NUDGE_PULSE",
            "outcome": "NO_CHANGE",
            "deltas": {"occupancy_shift_cells": 0},
            "parameters": {"pulse_ms": 50},
        }
    )

    assert result.ok


def test_validate_runtime_snapshot_v1() -> None:
    result = validate_event(
        {
            "kind": "RUNTIME_STATE_SNAPSHOT",
            "t": 0,
            "timebase": "DEVICE_TICKS",
            "run_id": "R1",
            "rimgb_hash": "sha256:abc",
            "state_fields": {"temperature_c": 25.0},
            "validity_window": {"start_t": 0, "end_t": 10},
        }
    )

    assert result.ok


def test_validate_run_start_v1() -> None:
    result = validate_event(
        {
            "kind": "RUN_START",
            "t": 0,
            "timebase": "DEVICE_TICKS",
            "run_id": "R1",
            "artifact_hash": "sha256:abc",
            "artifact_canonicalization": "klein.canon.json.v1",
            "artifact_type": "container",
            "profile_id": "dmf",
            "profile_version": "v1",
            "backend_id": "full_simulator",
            "backend_version": "1.0.0a0",
            "mode": "HARD",
            "substrate_fingerprint": "sha256:def",
            "substrate_fingerprint_canonicalization": "klein.canon.json.v1",
        }
    )

    assert result.ok


def test_validate_run_end_v1() -> None:
    result = validate_event(
        {
            "kind": "RUN_END",
            "t": 2,
            "timebase": "DEVICE_TICKS",
            "run_id": "R1",
            "status": "SUCCESS",
            "error_code": None,
            "preclose_hail_digest": "sha256:abc",
            "preclose_hail_canonicalization": "klein.canon.jsonl.v1",
            "preclose_hail_chain_digest": "sha256:def",
            "preclose_hail_chain_algorithm": "klein.hail.chain.v1",
            "event_count_preclose": 4,
        }
    )

    assert result.ok


def test_legacy_rsb_snapshot_rejected_in_v1() -> None:
    result = validate_event(
        {
            "kind": "RUNTIME_STATE_SNAPSHOT",
            "t": 0,
            "timebase": "DEVICE_TICKS",
            "run_id": "R1",
            "rsb_hash": "sha256:abc",
            "fields": {"temperature_c": 25.0},
            "valid_from_t": 0,
            "valid_to_t": 10,
        }
    )

    assert not result.ok
    assert result.error_code == HAIL_SCHEMA_INVALID


def test_legacy_rsb_snapshot_normalizes_explicitly() -> None:
    legacy = {
        "kind": "RUNTIME_STATE_SNAPSHOT",
        "t": 0,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "rsb_hash": "sha256:abc",
        "fields": {"temperature_c": 25.0},
        "valid_from_t": 0,
        "valid_to_t": 10,
    }

    normalized = normalize_legacy_event(legacy)

    assert "rsb_hash" not in normalized
    assert normalized["rimgb_hash"] == "sha256:abc"
    assert normalized["state_fields"] == {"temperature_c": 25.0}
    assert normalized["validity_window"] == {"start_t": 0, "end_t": 10}
    assert validate_event(normalized).ok


def test_canonical_key_ordering_is_stable() -> None:
    assert dump_canonical({"b": 2, "a": 1}) == '{"a":1,"b":2}'


def test_canonical_number_and_unicode_behavior_is_jcs() -> None:
    assert dump_canonical({"integer": 1, "float": 1.5, "unicode": "µ"}) == (
        '{"float":1.5,"integer":1,"unicode":"µ"}'
    )


def test_canonical_rejects_non_finite_numbers() -> None:
    with pytest.raises(ValueError):
        dump_canonical({"value": math.nan})


def test_canonical_event_ordering_is_deterministic() -> None:
    events = [
        {"kind": "MEASUREMENT", "t": 1, "measurement_id": "B"},
        {"kind": "DEVICE_EVENT", "t": 1, "code": "INIT"},
        {"kind": "MEASUREMENT", "t": 1, "measurement_id": "A"},
    ]

    canonical = canonicalize_events(events)

    assert canonical == [
        '{"code":"INIT","kind":"DEVICE_EVENT","t":1}',
        '{"kind":"MEASUREMENT","measurement_id":"A","t":1}',
        '{"kind":"MEASUREMENT","measurement_id":"B","t":1}',
    ]


def test_lifecycle_events_order_first_and_last_at_same_tick() -> None:
    events = [
        {"kind": "RUN_END", "t": 0, "run_id": "R1"},
        {"kind": "DEVICE_EVENT", "t": 0, "code": "INIT"},
        {"kind": "RUN_START", "t": 0, "run_id": "R1"},
        {"kind": "RUNTIME_STATE_SNAPSHOT", "t": 0, "rimgb_hash": "sha256:state"},
    ]

    canonical = canonicalize_events(events)

    assert '"kind":"RUN_START"' in canonical[0]
    assert '"kind":"RUN_END"' in canonical[-1]


def test_rimgb_hash_is_runtime_snapshot_tie_breaker() -> None:
    events = [
        {"kind": "RUNTIME_STATE_SNAPSHOT", "t": 0, "rimgb_hash": "z"},
        {"kind": "RUNTIME_STATE_SNAPSHOT", "t": 0, "rimgb_hash": "a"},
    ]

    assert canonicalize_events(events)[0] == '{"kind":"RUNTIME_STATE_SNAPSHOT","rimgb_hash":"a","t":0}'


def test_normalized_hail_digest_is_stable() -> None:
    events_a = [{"kind": "DEVICE_EVENT", "t": 0, "run_id": "random-a", "code": "INIT"}]
    events_b = [{"kind": "DEVICE_EVENT", "t": 0, "run_id": "random-b", "code": "INIT"}]

    assert compute_digest(normalize_run_metadata(events_a)) == compute_digest(
        normalize_run_metadata(events_b)
    )


def test_validate_events_reports_first_bad_event() -> None:
    result = validate_events(
        [
            {
                "kind": "DEVICE_EVENT",
                "t": 0,
                "timebase": "DEVICE_TICKS",
                "run_id": "R1",
                "code": "INIT",
                "level": "INFO",
                "message": "ok",
            },
            {"kind": "DEVICE_EVENT", "t": 1, "timebase": "DEVICE_TICKS", "run_id": "R1"},
        ]
    )

    assert not result.ok
    assert result.index == 1


def test_parse_jsonl_events_returns_validated_events() -> None:
    payload = (
        '{"kind":"DEVICE_EVENT","t":0,"timebase":"DEVICE_TICKS",'
        '"run_id":"R1","code":"INIT","level":"INFO","message":"ok"}\n'
    )

    result, events = parse_jsonl_events(payload)

    assert result.ok
    assert events[0]["kind"] == "DEVICE_EVENT"


def test_parse_jsonl_events_rejects_duplicate_object_names() -> None:
    payload = (
        '{"kind":"DEVICE_EVENT","kind":"DEVICE_EVENT","t":0,"timebase":"DEVICE_TICKS",'
        '"run_id":"R1","code":"INIT","level":"INFO","message":"ok"}\n'
    )

    result, events = parse_jsonl_events(payload)

    assert not result.ok
    assert result.error_code == HAIL_JSON_INVALID
    assert events == []


def test_parse_jsonl_events_rejects_non_finite_numbers() -> None:
    payload = (
        '{"kind":"MEASUREMENT","t":0,"timebase":"DEVICE_TICKS","run_id":"R1",'
        '"detector_id":"sensor","value":{"type":"F64","data":NaN}}\n'
    )

    result, events = parse_jsonl_events(payload)

    assert not result.ok
    assert result.error_code == HAIL_JSON_INVALID
    assert events == []

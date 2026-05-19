from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator
from jsonschema.exceptions import ValidationError as JSONSchemaValidationError
from pydantic import ValidationError as PydanticValidationError
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT7

from klein.common.models import Container
from klein.hail.validation import validate_event

SCHEMA_DIR = Path("schemas").resolve()


def load_schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def schema_with_id(name: str) -> dict:
    schema = load_schema(name)
    schema.setdefault("$id", (SCHEMA_DIR / name).as_uri())
    return schema


def schema_registry() -> Registry:
    resources = []
    for path in SCHEMA_DIR.glob("*.schema.json"):
        schema = schema_with_id(path.name)
        resources.append((
            path.as_uri(),
            Resource.from_contents(schema, default_specification=DRAFT7),
        ))
    return Registry().with_resources(resources)


def assert_jsonschema_valid(schema_name: str, instance: dict) -> None:
    schema = schema_with_id(schema_name)
    Draft7Validator(schema, registry=schema_registry()).validate(instance)


def assert_jsonschema_invalid(schema_name: str, instance: dict) -> None:
    with pytest.raises(JSONSchemaValidationError):
        assert_jsonschema_valid(schema_name, instance)


def test_device_event_schema_parity_valid() -> None:
    event = {
        "kind": "DEVICE_EVENT",
        "t": 0,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "code": "INIT",
        "level": "INFO",
        "message": "ok",
    }

    assert validate_event(event).ok
    assert_jsonschema_valid("hail_events.schema.json", event)


def test_device_event_missing_message_invalid_in_both() -> None:
    event = {
        "kind": "DEVICE_EVENT",
        "t": 0,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "code": "INIT",
        "level": "INFO",
    }

    assert not validate_event(event).ok
    assert_jsonschema_invalid("hail_events.schema.json", event)


def test_runtime_snapshot_schema_parity_valid() -> None:
    event = {
        "kind": "RUNTIME_STATE_SNAPSHOT",
        "t": 0,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "rimgb_hash": "sha256:abc",
        "state_fields": {"status": "ready"},
        "validity_window": {"start_t": 0, "end_t": 0},
    }

    assert validate_event(event).ok
    assert_jsonschema_valid("hail_events.schema.json", event)


def test_run_start_schema_parity_valid() -> None:
    event = {
        "kind": "RUN_START",
        "t": 0,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "artifact_hash": "sha256:artifact",
        "artifact_canonicalization": "klein.canon.json.v1",
        "artifact_type": "container",
        "profile_id": "dmf",
        "profile_version": "v1",
        "backend_id": "full_simulator",
        "backend_version": "1.0.0a0",
        "mode": "HARD",
        "substrate_capabilities_hash": "sha256:caps",
        "substrate_topology_hash": "sha256:topology",
        "substrate_fingerprint": "sha256:fingerprint",
        "substrate_fingerprint_canonicalization": "klein.canon.json.v1",
    }

    assert validate_event(event).ok
    assert_jsonschema_valid("hail_events.schema.json", event)


def test_run_end_schema_parity_valid() -> None:
    event = {
        "kind": "RUN_END",
        "t": 2,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "status": "FAIL",
        "error_code": "CHANNEL_DEAD",
        "preclose_hail_digest": "sha256:preclose",
        "preclose_hail_canonicalization": "klein.canon.jsonl.v1",
        "preclose_hail_chain_digest": "sha256:chain",
        "preclose_hail_chain_algorithm": "klein.hail.chain.v1",
        "event_count_preclose": 6,
    }

    assert validate_event(event).ok
    assert_jsonschema_valid("hail_events.schema.json", event)


def test_legacy_rsb_snapshot_invalid_in_both() -> None:
    event = {
        "kind": "RUNTIME_STATE_SNAPSHOT",
        "t": 0,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "rsb_hash": "sha256:legacy",
        "fields": {"status": "legacy"},
        "valid_from_t": 0,
        "valid_to_t": 1,
    }

    assert not validate_event(event).ok
    assert_jsonschema_invalid("hail_events.schema.json", event)


def test_ecrp_no_change_schema_parity_valid() -> None:
    event = {
        "kind": "ECRP_ATTEMPT",
        "t": 1,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "attempt_index": 1,
        "strategy": "NUDGE_PULSE",
        "outcome": "NO_CHANGE",
        "deltas": {"occupancy_shift_cells": 0},
        "parameters": {"pulse_ms": 50},
    }

    assert validate_event(event).ok
    assert_jsonschema_valid("hail_events.schema.json", event)


def test_replan_decision_schema_parity_valid() -> None:
    event = {
        "kind": "REPLAN_DECISION",
        "t": 1,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "checkpoint_id": "solve_1",
        "reason": "geodesic_solve",
        "solver_version": "klein-sim/1.0.0",
        "solver_mode": "GEODESIC",
        "seed": 42,
        "inputs_ref": {
            "simgb_hash": "null",
            "rimgb_hash": "sha256:abc",
            "observables_snapshot": {},
        },
    }

    assert validate_event(event).ok
    assert_jsonschema_valid("hail_events.schema.json", event)


def test_measurement_schema_parity_valid() -> None:
    event = {
        "kind": "MEASUREMENT",
        "t": 1,
        "timebase": "DEVICE_TICKS",
        "run_id": "R1",
        "detector_id": "geodesic_solver",
        "measurement_id": "m1",
        "value": {"type": "F64", "data": 1.0},
    }

    assert validate_event(event).ok
    assert_jsonschema_valid("hail_events.schema.json", event)


def minimal_container() -> dict:
    return {
        "klein_container_version": "1.0",
        "manifest": {
            "project": {"name": "schema-parity", "version": "1.0", "authors": ["Klein"]},
            "runtime": {"mode": "HARD", "target_substrate": "dmf.muxed_ewod.opendrop.v1.0"},
        },
        "payload": {"kind": "CHANNEL_LIST", "encoding": "JSON", "data": []},
    }


def test_minimal_container_schema_parity_valid() -> None:
    container = minimal_container()

    Container.model_validate(container)
    assert_jsonschema_valid("container.schema.json", container)


def test_unsupported_payload_kind_invalid_in_both() -> None:
    container = minimal_container()
    container["payload"]["kind"] = "RUNBOOK_FSM"

    with pytest.raises(PydanticValidationError):
        Container.model_validate(container)
    assert_jsonschema_invalid("container.schema.json", container)

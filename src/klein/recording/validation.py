"""Recorded Device Run v1 validation."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from klein.common.hashing import (
    HashResult,
    hash_json_value,
    parse_ijson,
    raw_file_sha256,
)
from klein.hil import canonical_hil_contract_hash
from klein.verifier import verify_bundle_independently

RECORDED_RUN_VERSION = "klein.recorded_device_run.v1"
RAW_DEVICE_LOG_VERSION = "klein.raw_device_log.v1"
SOURCE_TYPES = {"simulator", "mock_hardware", "hardware"}
RAW_OPERATIONS = {
    "connect",
    "apply_frame",
    "read_observation",
    "emergency_stop",
    "reset",
    "disconnect",
    "OPENDROP_CONNECT_DRY_RUN",
    "OPENDROP_SET_ELECTRODES",
    "OPENDROP_APPLY_FRAME",
    "OPENDROP_CLEAR_ELECTRODES",
    "OPENDROP_ESTOP",
    "OPENDROP_RESET",
    "OPENDROP_READ_MOCK_OBSERVATION",
}


class RecordedRunValidationError(ValueError):
    """Structured Recorded Device Run validation failure."""

    def __init__(self, error_code: str, message: str):
        super().__init__(message)
        self.error_code = error_code


@dataclass(frozen=True)
class RecordedRunValidationResult:
    ok: bool
    error_code: str | None = None
    message: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


def load_recorded_run_json(path: str | Path) -> dict[str, Any]:
    data = parse_ijson(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RecordedRunValidationError("RECORDED_RUN_SCHEMA_INVALID", "recorded run root must be an object")
    return data


def canonical_recorded_run_hash(data: dict[str, Any]) -> HashResult:
    return hash_json_value(data)


def raw_device_log_hash(path: str | Path) -> HashResult:
    return raw_file_sha256(Path(path))


def validate_recorded_device_run(
    data: dict[str, Any],
    *,
    strict_current_alpha: bool = True,
) -> RecordedRunValidationResult:
    if data.get("recorded_run_version") != RECORDED_RUN_VERSION:
        return _failure("RECORDED_RUN_SCHEMA_INVALID", "unsupported recorded_run_version")
    required = (
        "recorded_run_id",
        "source_type",
        "source_id",
        "source_version",
        "hardware_claimed",
        "attestation",
        "trusted_timestamp",
        "bundle_ref",
        "artifact_hash",
        "runbook_hash",
        "trace_hash",
        "observation_hashes",
        "hil_contract_hash",
        "hil_status_hash",
        "raw_device_logs",
        "media",
        "notes",
    )
    for field_name in required:
        if field_name not in data:
            return _failure("RECORDED_RUN_SCHEMA_INVALID", f"missing required field {field_name}")
    source_type = data.get("source_type")
    if source_type not in SOURCE_TYPES:
        return _failure("RECORDED_RUN_SCHEMA_INVALID", "source_type is invalid")
    if strict_current_alpha and source_type == "hardware":
        return _failure("RECORDED_RUN_HARDWARE_CLAIM_UNSUPPORTED", "hardware source_type is not supported in CURRENT_ALPHA")
    if strict_current_alpha and data.get("hardware_claimed") is True:
        return _failure("RECORDED_RUN_HARDWARE_CLAIM_UNSUPPORTED", "hardware_claimed must be false in CURRENT_ALPHA")
    if strict_current_alpha and data.get("attestation") is not None:
        return _failure("RECORDED_RUN_ATTESTATION_UNSUPPORTED", "attestation must be null in CURRENT_ALPHA")
    if strict_current_alpha and data.get("trusted_timestamp") is not None:
        return _failure("RECORDED_RUN_TIMESTAMP_UNSUPPORTED", "trusted_timestamp must be null in CURRENT_ALPHA")
    bundle_ref = data.get("bundle_ref")
    if bundle_ref is not None:
        if not isinstance(bundle_ref, dict):
            return _failure("RECORDED_RUN_SCHEMA_INVALID", "bundle_ref must be object or null")
        path_error = _relative_path_error(bundle_ref.get("path"))
        if path_error is not None:
            return _failure("RECORDED_RUN_SCHEMA_INVALID", path_error)
        if not _sha_ref(bundle_ref.get("sha256")):
            return _failure("RECORDED_RUN_SCHEMA_INVALID", "bundle_ref.sha256 must be sha256:<hex>")
    for field_name in ("artifact_hash", "runbook_hash", "trace_hash", "hil_contract_hash", "hil_status_hash"):
        value = data.get(field_name)
        if value is not None and not _sha_ref(value):
            return _failure("RECORDED_RUN_SCHEMA_INVALID", f"{field_name} must be sha256:<hex> or null")
    if not isinstance(data.get("observation_hashes"), list) or any(not _sha_ref(value) for value in data["observation_hashes"]):
        return _failure("RECORDED_RUN_SCHEMA_INVALID", "observation_hashes must be sha256 refs")
    raw_logs = data.get("raw_device_logs")
    if not isinstance(raw_logs, list):
        return _failure("RECORDED_RUN_SCHEMA_INVALID", "raw_device_logs must be an array")
    for raw_log in raw_logs:
        result = _validate_raw_log_ref(raw_log, strict_current_alpha=strict_current_alpha)
        if not result.ok:
            return result
    return RecordedRunValidationResult(ok=True)


def validate_raw_device_log_jsonl(
    path_or_events: str | Path | list[dict[str, Any]],
    *,
    strict_current_alpha: bool = True,
) -> RecordedRunValidationResult:
    try:
        events = _load_raw_events(path_or_events)
    except (OSError, json.JSONDecodeError, RecordedRunValidationError) as exc:
        return _failure("RAW_DEVICE_LOG_INVALID", str(exc))
    expected_index = 1
    for event in events:
        if event.get("raw_log_version") != RAW_DEVICE_LOG_VERSION:
            return _failure("RAW_DEVICE_LOG_SCHEMA_INVALID", "unsupported raw_log_version")
        if event.get("event_index") != expected_index:
            return _failure("RAW_DEVICE_LOG_ORDER_INVALID", "raw log event_index must be strictly monotonic from 1")
        expected_index += 1
        if event.get("source_type") not in SOURCE_TYPES:
            return _failure("RAW_DEVICE_LOG_SCHEMA_INVALID", "raw log source_type is invalid")
        if strict_current_alpha and event.get("source_type") == "hardware":
            return _failure("RECORDED_RUN_HARDWARE_CLAIM_UNSUPPORTED", "hardware raw log source_type is not supported in CURRENT_ALPHA")
        if event.get("operation") not in RAW_OPERATIONS:
            return _failure("RAW_DEVICE_LOG_SCHEMA_INVALID", "raw log operation is invalid")
        if event.get("status") not in {"OK", "ERROR"}:
            return _failure("RAW_DEVICE_LOG_SCHEMA_INVALID", "raw log status must be OK or ERROR")
        if event.get("status") == "ERROR" and not event.get("error_code"):
            return _failure("RAW_DEVICE_LOG_ERROR_CODE_MISSING", "ERROR raw log event requires error_code")
        if not isinstance(event.get("tick"), int) or event["tick"] < 0:
            return _failure("RAW_DEVICE_LOG_SCHEMA_INVALID", "raw log tick must be a non-negative integer")
        if not isinstance(event.get("details"), dict):
            return _failure("RAW_DEVICE_LOG_SCHEMA_INVALID", "raw log details must be an object")
    return RecordedRunValidationResult(ok=True, details={"event_count": len(events)})


def inspect_recorded_run(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "recorded_run_id": data.get("recorded_run_id"),
        "source_type": data.get("source_type"),
        "source_id": data.get("source_id"),
        "hardware_claimed": data.get("hardware_claimed"),
        "attestation_status": "present" if data.get("attestation") is not None else "absent",
        "trusted_timestamp_status": "present" if data.get("trusted_timestamp") is not None else "absent",
        "bundle_present": data.get("bundle_ref") is not None,
        "raw_log_count": len(data.get("raw_device_logs", [])) if isinstance(data.get("raw_device_logs"), list) else 0,
        "recorded_run_hash": canonical_recorded_run_hash(data).ref,
    }


def validate_recorded_run_package(
    path: str | Path,
    *,
    strict_current_alpha: bool = True,
    verify_bundle: bool = False,
) -> RecordedRunValidationResult:
    root = Path(path)
    if root.is_file():
        data = load_recorded_run_json(root)
        return validate_recorded_device_run(data, strict_current_alpha=strict_current_alpha)
    recorded_run_path = root / "recorded_run.json"
    if not recorded_run_path.exists():
        return _failure("RECORDED_RUN_INVALID", "recorded_run.json is required")
    data = load_recorded_run_json(recorded_run_path)
    result = validate_recorded_device_run(data, strict_current_alpha=strict_current_alpha)
    if not result.ok:
        return result
    details = {
        "recorded_run_status": "pass",
        "bundle_present": data.get("bundle_ref") is not None,
        "bundle_verification_status": "not_requested",
        "raw_log_status": "pass",
        "hardware_claim_status": "pass",
        "attestation_status": "pass",
        "timestamp_status": "pass",
    }
    bundle_ref = data.get("bundle_ref")
    if bundle_ref is not None:
        bundle_path = _resolve_package_path(root, bundle_ref["path"])
        if not bundle_path.exists():
            return _failure("RECORDED_RUN_BUNDLE_MISSING", f"bundle is missing: {bundle_ref['path']}", details)
        if raw_file_sha256(bundle_path).ref != bundle_ref["sha256"]:
            return _failure("RECORDED_RUN_BUNDLE_INVALID", "bundle hash mismatch", details)
        if verify_bundle:
            verification = verify_bundle_independently(bundle_path, require_backend_capabilities=True)
            details["bundle_verification_status"] = verification.overall_status
            if not verification.ok:
                return _failure("RECORDED_RUN_BUNDLE_INVALID", "bundle verification failed", details)
    for raw_log in data["raw_device_logs"]:
        log_path = _resolve_package_path(root, raw_log["path"])
        if not log_path.exists():
            return _failure("RAW_DEVICE_LOG_INVALID", f"raw device log is missing: {raw_log['path']}", details)
        if raw_file_sha256(log_path).ref != raw_log["sha256"]:
            return _failure("RAW_DEVICE_LOG_HASH_MISMATCH", "raw device log hash mismatch", details)
        raw_result = validate_raw_device_log_jsonl(log_path, strict_current_alpha=strict_current_alpha)
        if not raw_result.ok:
            return raw_result
    observation_hashes = list(data.get("observation_hashes", []))
    observation_paths = sorted((root / "observations").glob("*.json")) if (root / "observations").exists() else []
    if observation_hashes and len(observation_paths) != len(observation_hashes):
        return _failure("RECORDED_RUN_INVALID", "observation_hashes do not match packaged observations", details)
    for expected, observation_path in zip(observation_hashes, observation_paths, strict=True):
        observation_data = parse_ijson(observation_path.read_text(encoding="utf-8"))
        if hash_json_value(observation_data).ref != expected:
            return _failure("RECORDED_RUN_INVALID", "observation hash mismatch", details)
    if data.get("hil_contract_hash") is not None:
        contract_path = root / "hil" / "hil_contract.json"
        if not contract_path.exists():
            return _failure("RECORDED_RUN_INVALID", "hil_contract_hash declared but hil/hil_contract.json is missing", details)
        contract_data = parse_ijson(contract_path.read_text(encoding="utf-8"))
        if canonical_hil_contract_hash(contract_data).ref != data["hil_contract_hash"]:
            return _failure("RECORDED_RUN_INVALID", "HIL contract hash mismatch", details)
    if data.get("hil_status_hash") is not None:
        status_path = root / "hil" / "hil_status.json"
        if not status_path.exists():
            return _failure("RECORDED_RUN_INVALID", "hil_status_hash declared but hil/hil_status.json is missing", details)
        status_data = parse_ijson(status_path.read_text(encoding="utf-8"))
        if hash_json_value(status_data).ref != data["hil_status_hash"]:
            return _failure("RECORDED_RUN_INVALID", "HIL status hash mismatch", details)
    return RecordedRunValidationResult(ok=True, details=details)


def create_mock_recorded_run(bundle_path: str | Path, output: str | Path) -> Path:
    from klein.hil import MockHilBackend
    from klein.substrate.api import Frame

    bundle = Path(bundle_path)
    root = Path(output)
    if root.exists() and any(root.iterdir()):
        raise RecordedRunValidationError("RECORDED_RUN_INVALID", f"output directory is not empty: {root}")
    (root / "run").mkdir(parents=True, exist_ok=True)
    (root / "raw").mkdir(parents=True, exist_ok=True)
    (root / "observations").mkdir(parents=True, exist_ok=True)
    (root / "hil").mkdir(parents=True, exist_ok=True)
    (root / "media").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(bundle, root / "run" / "run.kcprun")
    backend = MockHilBackend()
    backend.connect()
    backend.apply_frame(Frame(seq=1, active_electrodes=(1, 2, 3), duration_ms=10))
    observation = backend.read_observation()
    contract = backend.contract()
    status = backend.status()
    raw_events = [
        _raw_event(1, "connect", "OK", 0, {"mock": True}),
        _raw_event(2, "apply_frame", "OK", 1, {"seq": 1, "active_electrodes": [1, 2, 3]}),
        _raw_event(3, "read_observation", "OK", 1, {"observation_id": observation["observation_id"]}),
    ]
    _write_json(root / "observations" / "observation-0001.json", observation)
    _write_json(root / "hil" / "hil_contract.json", contract)
    _write_json(root / "hil" / "hil_status.json", status)
    _write_jsonl(root / "raw" / "device-log.jsonl", raw_events)
    recorded = {
        "recorded_run_version": RECORDED_RUN_VERSION,
        "recorded_run_id": "mock-recorded-run",
        "source_type": "mock_hardware",
        "source_id": backend.backend_id,
        "source_version": backend.backend_version,
        "hardware_claimed": False,
        "attestation": None,
        "trusted_timestamp": None,
        "bundle_ref": {"path": "run/run.kcprun", "sha256": raw_file_sha256(root / "run" / "run.kcprun").ref},
        "artifact_hash": _artifact_hash_from_bundle(bundle),
        "runbook_hash": None,
        "trace_hash": None,
        "observation_hashes": [hash_json_value(observation).ref],
        "hil_contract_hash": canonical_hil_contract_hash(contract).ref,
        "hil_status_hash": hash_json_value(status).ref,
        "raw_device_logs": [
            {
                "log_id": "log-0001",
                "path": "raw/device-log.jsonl",
                "sha256": raw_file_sha256(root / "raw" / "device-log.jsonl").ref,
                "log_format": "jsonl",
                "source_type": "mock_hardware",
            }
        ],
        "media": [],
        "notes": ["Mock recorded run fixture. No hardware, attestation, timestamp, or physical proof is claimed."],
    }
    _write_json(root / "recorded_run.json", recorded)
    (root / "media" / "README.md").write_text("No media is included in this mock fixture.\n", encoding="utf-8")
    return root


def _artifact_hash_from_bundle(bundle_path: Path) -> str:
    result = verify_bundle_independently(bundle_path, require_backend_capabilities=True)
    value = result.bindings.get("artifact_hash")
    if isinstance(value, str) and _sha_ref(value):
        return value
    return "sha256:" + ("0" * 64)


def _validate_raw_log_ref(raw_log: Any, *, strict_current_alpha: bool) -> RecordedRunValidationResult:
    if not isinstance(raw_log, dict):
        return _failure("RECORDED_RUN_SCHEMA_INVALID", "raw_device_logs entries must be objects")
    for field_name in ("log_id", "path", "sha256", "log_format", "source_type"):
        if field_name not in raw_log:
            return _failure("RECORDED_RUN_SCHEMA_INVALID", f"raw device log ref missing {field_name}")
    path_error = _relative_path_error(raw_log.get("path"))
    if path_error is not None:
        return _failure("RECORDED_RUN_SCHEMA_INVALID", path_error)
    if raw_log.get("log_format") != "jsonl":
        return _failure("RECORDED_RUN_SCHEMA_INVALID", "raw device log format must be jsonl")
    if not _sha_ref(raw_log.get("sha256")):
        return _failure("RECORDED_RUN_SCHEMA_INVALID", "raw device log sha256 must be sha256:<hex>")
    if raw_log.get("source_type") not in SOURCE_TYPES:
        return _failure("RECORDED_RUN_SCHEMA_INVALID", "raw device log source_type is invalid")
    if strict_current_alpha and raw_log.get("source_type") == "hardware":
        return _failure("RECORDED_RUN_HARDWARE_CLAIM_UNSUPPORTED", "hardware raw log source_type is not supported in CURRENT_ALPHA")
    return RecordedRunValidationResult(ok=True)


def _load_raw_events(path_or_events: str | Path | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(path_or_events, list):
        return path_or_events
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path_or_events).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        event = parse_ijson(line)
        if not isinstance(event, dict):
            raise RecordedRunValidationError("RAW_DEVICE_LOG_SCHEMA_INVALID", f"line {line_number} is not an object")
        events.append(event)
    return events


def _relative_path_error(value: Any) -> str | None:
    if not isinstance(value, str) or not value:
        return "path must be a non-empty relative string"
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or ":" in value:
        return f"path is unsafe: {value}"
    return None


def _resolve_package_path(root: Path, relative: str) -> Path:
    path = root / PurePosixPath(relative).as_posix()
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise RecordedRunValidationError("RECORDED_RUN_SCHEMA_INVALID", f"path escapes package: {relative}") from exc
    return path


def _sha_ref(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 71 and value.startswith("sha256:") and all(char in "0123456789abcdef" for char in value[7:])


def _failure(error_code: str, message: str, details: dict[str, Any] | None = None) -> RecordedRunValidationResult:
    return RecordedRunValidationResult(ok=False, error_code=error_code, message=message, details=details or {})


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, events: list[dict[str, Any]]) -> None:
    path.write_text("".join(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in events), encoding="utf-8")


def _raw_event(index: int, operation: str, status: str, tick: int, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "raw_log_version": RAW_DEVICE_LOG_VERSION,
        "event_index": index,
        "source_type": "mock_hardware",
        "operation": operation,
        "status": status,
        "tick": tick,
        "details": details,
    }

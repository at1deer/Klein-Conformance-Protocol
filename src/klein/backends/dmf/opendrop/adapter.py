"""OpenDrop/EWOD dry-run adapter skeleton."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from klein.backends.dmf.adapter import AdapterRunResult
from klein.backends.dmf.opendrop.config import (
    OpenDropAdapterError,
    validate_opendrop_adapter_config,
)
from klein.backends.dmf.opendrop.mapping import (
    build_electrode_mapping,
    runbook_step_to_opendrop_intent,
)
from klein.backends.dmf.opendrop.serialization import serialize_intent_to_opendrop_command
from klein.backends.dmf.opendrop.transport import DEFAULT_TRANSPORT_CONFIG
from klein.backends.dmf.translation import raw_event
from klein.common.hashing import hash_json_value, raw_file_sha256
from klein.execution import canonical_runbook_hash, canonical_trace_hash
from klein.execution.observation import build_dmf_simulated_observation
from klein.hil import MockHilBackend, canonical_hil_contract_hash
from klein.recording.validation import RECORDED_RUN_VERSION, validate_recorded_run_package


class OpenDropEwodDryRunAdapter:
    """OpenDrop/EWOD dry-run skeleton. It never enables hardware IO."""

    def __init__(self, config: dict[str, Any]):
        result = validate_opendrop_adapter_config(config)
        if not result.ok:
            raise OpenDropAdapterError(result.error_code or "OPENDROP_ADAPTER_CONFIG_INVALID", result.message or "invalid OpenDrop adapter config")
        self.config = config
        self.mapping = build_electrode_mapping(config)
        self._hil = MockHilBackend()
        self._connected = False
        self._emergency_stopped = False
        self._last_error_code: str | None = None

    @property
    def adapter_id(self) -> str:
        return str(self.config["adapter_id"])

    @property
    def backend_id(self) -> str:
        return str(self.config["backend_id"])

    @property
    def backend_version(self) -> str:
        return str(self.config["backend_version"])

    def status(self) -> dict[str, Any]:
        health = "FAULTED" if self._last_error_code else ("OK" if self._connected else "UNKNOWN")
        return {
            "adapter_status_version": "klein.opendrop_adapter_status.v1",
            "adapter_id": self.adapter_id,
            "connected": self._connected,
            "hardware_io_enabled": False,
            "transport_status": "NONE",
            "health": health,
            "emergency_stopped": self._emergency_stopped,
            "last_error_code": self._last_error_code,
        }

    def hil_contract(self) -> dict[str, Any]:
        contract = self._hil.contract()
        contract["backend_id"] = self.backend_id
        contract["backend_version"] = self.backend_version
        contract["limitations"] = list(self.config["limitations"])
        return contract

    def connect(self) -> dict[str, Any]:
        self._connected = True
        return self._hil.connect()

    def emergency_stop(self) -> dict[str, Any]:
        self._connected = True
        self._emergency_stopped = True
        self._last_error_code = "OPENDROP_DRY_RUN_FAILED"
        return self._hil.emergency_stop()

    def reset(self) -> dict[str, Any]:
        self._connected = True
        self._emergency_stopped = False
        self._last_error_code = None
        return self._hil.reset()

    def run_runbook_dry(self, runbook: dict[str, Any], *, output_dir: str | Path | None = None) -> AdapterRunResult:
        if self._emergency_stopped:
            error_code = "DMF_ADAPTER_ESTOP_ACTIVE"
            return AdapterRunResult(
                ok=False,
                run_id="opendrop-ewod-dry-run",
                trace=self._empty_trace(runbook),
                raw_events=[raw_event(1, "OPENDROP_ESTOP", "ERROR", 0, {"adapter_id": self.adapter_id}, error_code=error_code)],
                observations=[],
                hil_contract=self.hil_contract(),
                hil_status=self.status(),
                error_code=error_code,
                message="emergency stop active",
            )
        self.connect()
        run_id = "opendrop-ewod-dry-run"
        raw_events = [raw_event(1, "OPENDROP_CONNECT_DRY_RUN", "OK", 0, {"adapter_id": self.adapter_id, "hardware_io_enabled": False})]
        trace_steps: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        event_index = 2
        for index, step in enumerate(runbook.get("planned_steps", []), start=1):
            tick = int(step.get("tick", index - 1))
            intent = runbook_step_to_opendrop_intent(step, self.mapping, self._electrical_context(step), seq=index)
            channel_ids = [electrode["channel_id"] for electrode in intent["electrodes"]]
            active_channels = [channel_id - 1 for channel_id in channel_ids]
            trace_steps.append({
                "step_id": step["step_id"],
                "runbook_step_id": step["step_id"],
                "tick": tick,
                "operation": step["operation"],
                "issued": True,
                "applied": True,
                "status": "APPLIED",
                "error_code": None,
                "details": {
                    "adapter_command": intent["operation"],
                    "intent_id": intent["intent_id"],
                    "electrode_ids": [electrode["electrode_id"] for electrode in intent["electrodes"]],
                    "channel_ids": channel_ids,
                    "dry_run": True,
                    "hardware_io_enabled": False,
                },
            })
            raw_events.append(raw_event(
                event_index,
                f"OPENDROP_{intent['operation']}",
                "OK",
                tick,
                {
                    "intent": intent,
                    "serial_command": serialize_intent_to_opendrop_command(intent, DEFAULT_TRANSPORT_CONFIG),
                    "dry_run": True,
                    "hardware_io_enabled": False,
                },
            ))
            event_index += 1
            observation = build_dmf_simulated_observation(
                observation_id=f"opendrop-adapter-obs-{index:04d}",
                run_id=run_id,
                tick=tick,
                runbook_step_id=step["step_id"],
                trace_step_id=step["step_id"],
                active_channels=active_channels,
                source_id=self.backend_id,
                source_version=self.backend_version,
                grid_width=int(self.config["electrode_layout"]["grid_width"]),
            )
            observation["metadata"]["opendrop_adapter"] = self.adapter_id
            observation["metadata"]["physical_hardware"] = False
            observations.append(observation)
            raw_events.append(raw_event(event_index, "OPENDROP_READ_MOCK_OBSERVATION", "OK", tick, {"observation_id": observation["observation_id"]}))
            event_index += 1
        trace = {
            "trace_version": "klein.execution_trace.v1",
            "trace_id": None,
            "run_id": run_id,
            "runbook_hash": canonical_runbook_hash(runbook).ref,
            "artifact_hash": runbook["source_artifact_hash"],
            "profile": dict(runbook["profile"]),
            "backend": {"backend_id": self.backend_id, "backend_version": self.backend_version},
            "timebase": "DEVICE_TICKS",
            "trace_steps": trace_steps,
            "metadata": {"opendrop_adapter": self.adapter_id, "dry_run": True, "hardware_io_enabled": False},
        }
        output_path = Path(output_dir) if output_dir is not None else None
        if output_path is not None:
            self._write_run_outputs(output_path, trace, raw_events, observations)
        return AdapterRunResult(
            ok=True,
            run_id=run_id,
            trace=trace,
            raw_events=raw_events,
            observations=observations,
            hil_contract=self.hil_contract(),
            hil_status=self.status(),
            output_dir=output_path,
            details={"trace_hash": canonical_trace_hash(trace).ref},
        )

    def create_recorded_run_from_adapter_result(
        self,
        result: AdapterRunResult,
        *,
        bundle_path: str | Path,
        output_dir: str | Path,
    ) -> Path:
        if not result.ok:
            raise OpenDropAdapterError("OPENDROP_RECORDING_FAILED", result.message or "dry-run adapter result failed")
        root = Path(output_dir)
        if root.exists() and any(root.iterdir()):
            raise OpenDropAdapterError("OPENDROP_RECORDING_FAILED", f"output directory is not empty: {root}")
        (root / "run").mkdir(parents=True, exist_ok=True)
        (root / "raw").mkdir(parents=True, exist_ok=True)
        (root / "observations").mkdir(parents=True, exist_ok=True)
        (root / "hil").mkdir(parents=True, exist_ok=True)
        (root / "backend").mkdir(parents=True, exist_ok=True)
        (root / "media").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle_path, root / "run" / "run.kcprun")
        self._write_run_outputs(root, result.trace, result.raw_events, result.observations)
        _write_json(root / "hil" / "hil_contract.json", result.hil_contract)
        _write_json(root / "hil" / "hil_status.json", result.hil_status)
        _write_json(root / "backend" / "opendrop_adapter_config.json", self.config)
        recorded = {
            "recorded_run_version": RECORDED_RUN_VERSION,
            "recorded_run_id": "opendrop-ewod-dry-run-recorded-run",
            "source_type": "mock_hardware",
            "source_id": self.backend_id,
            "source_version": self.backend_version,
            "hardware_claimed": False,
            "attestation": None,
            "trusted_timestamp": None,
            "bundle_ref": {"path": "run/run.kcprun", "sha256": raw_file_sha256(root / "run" / "run.kcprun").ref},
            "artifact_hash": result.trace["artifact_hash"],
            "runbook_hash": result.trace["runbook_hash"],
            "trace_hash": canonical_trace_hash(result.trace).ref,
            "observation_hashes": [hash_json_value(observation).ref for observation in result.observations],
            "hil_contract_hash": canonical_hil_contract_hash(result.hil_contract).ref,
            "hil_status_hash": hash_json_value(result.hil_status).ref,
            "raw_device_logs": [{
                "log_id": "log-0001",
                "path": "raw/device-log.jsonl",
                "sha256": raw_file_sha256(root / "raw" / "device-log.jsonl").ref,
                "log_format": "jsonl",
                "source_type": "mock_hardware",
            }],
            "media": [],
            "notes": ["Generated by OpenDrop/EWOD dry-run adapter skeleton. No OpenDrop hardware IO or physical execution is claimed."],
        }
        _write_json(root / "recorded_run.json", recorded)
        (root / "media" / "README.md").write_text("No media is included in this OpenDrop/EWOD dry-run fixture.\n", encoding="utf-8")
        package_result = validate_recorded_run_package(root)
        if not package_result.ok:
            raise OpenDropAdapterError(package_result.error_code or "OPENDROP_RECORDING_FAILED", package_result.message or "recorded-run validation failed")
        return root

    def _empty_trace(self, runbook: dict[str, Any]) -> dict[str, Any]:
        return {
            "trace_version": "klein.execution_trace.v1",
            "trace_id": None,
            "run_id": "opendrop-ewod-dry-run",
            "runbook_hash": canonical_runbook_hash(runbook).ref,
            "artifact_hash": runbook["source_artifact_hash"],
            "profile": dict(runbook["profile"]),
            "backend": {"backend_id": self.backend_id, "backend_version": self.backend_version},
            "timebase": "DEVICE_TICKS",
            "trace_steps": [],
            "metadata": {"opendrop_adapter": self.adapter_id, "dry_run": True},
        }

    def _electrical_context(self, step: dict[str, Any]) -> dict[str, Any]:
        details = step.get("expected_effect", {}).get("details", {})
        limits = self.config["electrical_limits"]
        return {
            "voltage_v": details.get("voltage_v", 120) if isinstance(details, dict) else 120,
            "frequency_hz": details.get("frequency_hz", 1000) if isinstance(details, dict) else 1000,
            "voltage_min_v": limits["voltage_min_v"],
            "voltage_max_v": limits["voltage_max_v"],
            "frequency_min_hz": limits["frequency_min_hz"],
            "frequency_max_hz": limits["frequency_max_hz"],
        }

    def _write_run_outputs(self, root: Path, trace: dict[str, Any], raw_events: list[dict[str, Any]], observations: list[dict[str, Any]]) -> None:
        (root / "raw").mkdir(parents=True, exist_ok=True)
        (root / "observations").mkdir(parents=True, exist_ok=True)
        _write_json(root / "trace.json", trace)
        (root / "raw" / "device-log.jsonl").write_text("".join(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in raw_events), encoding="utf-8")
        for index, observation in enumerate(observations, start=1):
            _write_json(root / "observations" / f"observation-{index:04d}.json", observation)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

"""Generic DMF dry-run backend adapter skeleton."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from klein.backends.dmf.adapter import AdapterRunResult
from klein.backends.dmf.config import (
    DmfAdapterError,
    validate_dmf_backend_adapter_config,
)
from klein.backends.dmf.translation import raw_event, runbook_step_to_frame
from klein.common.hashing import hash_json_value, raw_file_sha256
from klein.execution import canonical_runbook_hash, canonical_trace_hash
from klein.execution.observation import build_dmf_simulated_observation
from klein.hil import MockHilBackend, canonical_hil_contract_hash
from klein.recording.validation import RECORDED_RUN_VERSION, validate_recorded_run_package


class GenericDmfDryRunAdapter:
    """Dry-run DMF adapter skeleton. It never enables hardware IO."""

    def __init__(self, config: dict[str, Any]):
        result = validate_dmf_backend_adapter_config(config)
        if not result.ok:
            raise DmfAdapterError(result.error_code or "DMF_ADAPTER_CONFIG_INVALID", result.message or "invalid adapter config")
        self.config = config
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
        health = "UNKNOWN"
        if self._connected:
            health = "FAULTED" if self._last_error_code else "OK"
        return {
            "adapter_status_version": "klein.dmf_backend_adapter_status.v1",
            "adapter_id": self.adapter_id,
            "connected": self._connected,
            "hardware_io_enabled": False,
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
        self._last_error_code = "DMF_ADAPTER_ESTOP_ACTIVE"
        return self._hil.emergency_stop()

    def reset(self) -> dict[str, Any]:
        self._connected = True
        self._emergency_stopped = False
        self._last_error_code = None
        return self._hil.reset()

    def run_runbook_dry(self, runbook: dict[str, Any], *, output_dir: str | Path | None = None) -> AdapterRunResult:
        if self._emergency_stopped:
            return AdapterRunResult(
                ok=False,
                run_id="dmf-dry-run",
                trace=self._empty_trace(runbook),
                raw_events=[raw_event(1, "emergency_stop", "ERROR", 0, {"adapter_id": self.adapter_id}, error_code="DMF_ADAPTER_ESTOP_ACTIVE")],
                observations=[],
                hil_contract=self.hil_contract(),
                hil_status=self.status(),
                error_code="DMF_ADAPTER_ESTOP_ACTIVE",
                message="emergency stop active",
            )
        self.connect()
        run_id = "dmf-dry-run"
        max_channels = int(self.config["substrate"]["max_channels"])
        raw_events = [raw_event(1, "connect", "OK", 0, {"adapter_id": self.adapter_id, "dry_run": True})]
        trace_steps: list[dict[str, Any]] = []
        observations: list[dict[str, Any]] = []
        event_index = 2
        for index, step in enumerate(runbook.get("planned_steps", []), start=1):
            frame = runbook_step_to_frame(step, seq=index, max_channels=max_channels)
            ack = self._hil.apply_frame(frame)
            tick = int(step.get("tick", index - 1))
            status = "APPLIED" if ack.ok else "FAILED"
            error_code = None if ack.ok else "DMF_ADAPTER_DRY_RUN_FAILED"
            trace_steps.append({
                "step_id": step["step_id"],
                "runbook_step_id": step["step_id"],
                "tick": tick,
                "operation": step["operation"],
                "issued": True,
                "applied": ack.ok,
                "status": status,
                "error_code": error_code,
                "details": {"adapter_command": "apply_frame", "active_electrodes": list(frame.active_electrodes), "dry_run": True},
            })
            raw_events.append(raw_event(event_index, "apply_frame", "OK" if ack.ok else "ERROR", tick, {"seq": frame.seq, "active_electrodes": list(frame.active_electrodes)}, error_code=error_code))
            event_index += 1
            if ack.ok:
                observation = build_dmf_simulated_observation(
                    observation_id=f"dmf-adapter-obs-{index:04d}",
                    run_id=run_id,
                    tick=tick,
                    runbook_step_id=step["step_id"],
                    trace_step_id=step["step_id"],
                    active_channels=list(frame.active_electrodes),
                    source_id=self.backend_id,
                    source_version=self.backend_version,
                    grid_width=int(self.config["substrate"]["grid_width"]),
                )
                observation["metadata"]["dmf_backend_adapter"] = self.adapter_id
                observation["metadata"]["physical_hardware"] = False
                observations.append(observation)
                raw_events.append(raw_event(event_index, "read_observation", "OK", tick, {"observation_id": observation["observation_id"]}))
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
            "metadata": {"dmf_backend_adapter": self.adapter_id, "dry_run": True},
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
            raise DmfAdapterError("DMF_ADAPTER_RECORDING_FAILED", result.message or "dry-run adapter result failed")
        root = Path(output_dir)
        if root.exists() and any(root.iterdir()):
            raise DmfAdapterError("DMF_ADAPTER_RECORDING_FAILED", f"output directory is not empty: {root}")
        (root / "run").mkdir(parents=True, exist_ok=True)
        (root / "raw").mkdir(parents=True, exist_ok=True)
        (root / "observations").mkdir(parents=True, exist_ok=True)
        (root / "hil").mkdir(parents=True, exist_ok=True)
        (root / "media").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(bundle_path, root / "run" / "run.kcprun")
        self._write_run_outputs(root, result.trace, result.raw_events, result.observations)
        _write_json(root / "hil" / "hil_contract.json", result.hil_contract)
        _write_json(root / "hil" / "hil_status.json", result.hil_status)
        recorded = {
            "recorded_run_version": RECORDED_RUN_VERSION,
            "recorded_run_id": "dmf-dry-run-recorded-run",
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
            "notes": ["Generated by Generic DMF Dry-Run Adapter. No hardware IO or physical execution is claimed."],
        }
        _write_json(root / "recorded_run.json", recorded)
        (root / "media" / "README.md").write_text("No media is included in this dry-run fixture.\n", encoding="utf-8")
        package_result = validate_recorded_run_package(root)
        if not package_result.ok:
            raise DmfAdapterError(package_result.error_code or "DMF_ADAPTER_RECORDING_FAILED", package_result.message or "recorded-run validation failed")
        return root

    def _empty_trace(self, runbook: dict[str, Any]) -> dict[str, Any]:
        return {
            "trace_version": "klein.execution_trace.v1",
            "trace_id": None,
            "run_id": "dmf-dry-run",
            "runbook_hash": canonical_runbook_hash(runbook).ref,
            "artifact_hash": runbook["source_artifact_hash"],
            "profile": dict(runbook["profile"]),
            "backend": {"backend_id": self.backend_id, "backend_version": self.backend_version},
            "timebase": "DEVICE_TICKS",
            "trace_steps": [],
            "metadata": {"dmf_backend_adapter": self.adapter_id, "dry_run": True},
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

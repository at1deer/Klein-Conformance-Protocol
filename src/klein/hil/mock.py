"""Mock HIL backend for interface readiness tests only."""

from __future__ import annotations

from typing import Any

from klein.execution.observation import build_dmf_simulated_observation
from klein.substrate.api import Ack, Fault, FaultCode, Frame, MockSubstrate


class MockHilBackend:
    """Dry-run HIL backend that never claims physical hardware."""

    backend_id = "mock_hil_dmf"
    backend_version = "0.0.0"

    def __init__(self) -> None:
        self._substrate = MockSubstrate()
        self._connected = False
        self._emergency_stopped = False
        self._last_error_code: str | None = None
        self._raw_log: list[dict[str, Any]] = []
        self._last_frame: Frame | None = None

    def contract(self) -> dict[str, Any]:
        return {
            "hil_contract_version": "klein.hil_backend_contract.v1",
            "backend_id": self.backend_id,
            "backend_version": self.backend_version,
            "profile": {"profile_id": "dmf", "profile_version": "v1"},
            "supports": {
                "connect": True,
                "disconnect": True,
                "get_capabilities": True,
                "get_topology": True,
                "get_health": True,
                "apply_frame": True,
                "read_observation": True,
                "emergency_stop": True,
                "reset": True,
                "export_raw_device_log": False,
            },
            "observation_sources": ["mock_hardware"],
            "attestation": {"supported": False, "profiles": []},
            "safety": {"requires_emergency_stop": True, "requires_reset": True},
            "limitations": ["Interface contract only.", "No physical device is claimed."],
        }

    def status(self) -> dict[str, Any]:
        health = "UNKNOWN"
        if self._connected:
            health = "FAULTED" if self._last_error_code else "OK"
        return {
            "hil_status_version": "klein.hil_backend_status.v1",
            "backend_id": self.backend_id,
            "connected": self._connected,
            "health": health,
            "emergency_stopped": self._emergency_stopped,
            "last_error_code": self._last_error_code,
            "details": {"mock": True, "physical_hardware": False},
        }

    def connect(self) -> dict[str, Any]:
        self._substrate.connect("mock-hil://dmf")
        self._connected = True
        self._raw_log.append({"operation": "connect", "status": "ok"})
        return {"operation": "connect", "status": "ok", "mock": True}

    def disconnect(self) -> dict[str, Any]:
        self._connected = False
        self._raw_log.append({"operation": "disconnect", "status": "ok"})
        return {"operation": "disconnect", "status": "ok", "mock": True}

    def get_capabilities(self):
        if not self._connected:
            self.connect()
        return self._substrate.get_capabilities()

    def get_topology(self):
        if not self._connected:
            self.connect()
        return self._substrate.get_topology()

    def get_health(self) -> dict[str, Any]:
        return self.status()

    def apply_frame(self, frame: Frame) -> Ack:
        if not self._connected:
            self.connect()
        if self._emergency_stopped:
            self._last_error_code = "HIL_ESTOP_ACTIVE"
            ack = Ack(seq=frame.seq, ok=False, faults=(Fault(FaultCode.EXECUTION_ABORTED, "Mock HIL emergency stop active"),))
            self._raw_log.append({"operation": "apply_frame", "status": "blocked", "error_code": self._last_error_code})
            return ack
        ack = self._substrate.apply_frame(frame)
        self._last_frame = frame if ack.ok else None
        self._last_error_code = None if ack.ok else (ack.faults[0].code.value if ack.faults else "HIL_FRAME_FAILED")
        self._raw_log.append({"operation": "apply_frame", "status": "ok" if ack.ok else "fail", "seq": frame.seq})
        return ack

    def read_observation(self) -> dict[str, Any]:
        frame = self._last_frame or Frame(seq=1, active_electrodes=(), duration_ms=10)
        observation = build_dmf_simulated_observation(
            observation_id=f"hil-obs-{frame.seq:04d}",
            run_id="mock-hil-run",
            tick=frame.seq,
            runbook_step_id=f"step-{frame.seq:04d}",
            trace_step_id=f"step-{frame.seq:04d}",
            active_channels=list(frame.active_electrodes),
            source_id=self.backend_id,
            source_version=self.backend_version,
        )
        observation["source"]["source_type"] = "simulator"
        observation["metadata"]["hil_readiness_mock"] = True
        observation["metadata"]["physical_hardware"] = False
        self._raw_log.append({"operation": "read_observation", "status": "ok", "observation_id": observation["observation_id"]})
        return observation

    def emergency_stop(self) -> dict[str, Any]:
        if not self._connected:
            self.connect()
        self._emergency_stopped = True
        self._substrate.estop()
        self._raw_log.append({"operation": "emergency_stop", "status": "ok"})
        return {"operation": "emergency_stop", "status": "ok", "emergency_stopped": True, "mock": True}

    def reset(self) -> dict[str, Any]:
        if not self._connected:
            self.connect()
        self._emergency_stopped = False
        self._last_error_code = None
        self._substrate.reset()
        self._raw_log.append({"operation": "reset", "status": "ok"})
        return {"operation": "reset", "status": "ok", "emergency_stopped": False, "mock": True}

    def export_raw_device_log(self) -> list[dict[str, Any]]:
        return list(self._raw_log)

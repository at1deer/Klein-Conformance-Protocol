"""
Klein Execution Engine - Container validation and payload execution.

This module provides:
- Container loading and validation
- Payload parsing (ops → frame sequences)
- Frame-level execution with proper HAIL event emission
- ECRP (Error Correction & Recovery Protocol) integration

The execution engine bridges the gap between abstract Klein operations
and the concrete frame-level substrate API.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TextIO, Tuple

from klein.common.hashing import canonical_json_sha256_ref
from klein.common.models import (
    Container,
    Timebase,
)
from klein.profiles.dmf import (
    ChannelEntry,
    FrameEntry,
    FrameSequence,
    PayloadEncoding,
    PayloadKind,
    PayloadParser,
    context_from_substrate,
)
from klein.substrate.api import (
    Ack,
    Fault,
    FaultCode,
    Frame,
    SubstrateDriver,
)
from klein.sim.virtual_substrate import (
    KleinErrorCode,
    ValidationError,
    VirtualSubstrate,
)
from klein.hail.canonical import dump_canonical as dump_hail_canonical


# =============================================================================
# HAIL Event Emission
# =============================================================================

def compute_hash(data: Any) -> str:
    """Compute evidence-bound SHA-256 ref over JCS canonical JSON bytes."""
    return canonical_json_sha256_ref(data)


def dump_canonical(event: Dict[str, Any]) -> str:
    """Serialize event to canonical JSONL (RFC 8785)."""
    return dump_hail_canonical(event)


class HAILEmitter:
    """Emits HAIL (Hardware Audit & Integrity Log) events."""
    
    def __init__(self, output: TextIO, run_id: str, timebase: Timebase = "DEVICE_TICKS"):
        self._output = output
        self._run_id = run_id
        self._timebase = timebase
    
    def emit(self, event: Dict[str, Any]) -> None:
        """Emit a single event."""
        line = dump_canonical(event)
        self._output.write(line + "\n")
        self._output.flush()
    
    def emit_runtime_state_snapshot(
        self,
        t: int,
        rimgb_hash: str,
        state_fields: Optional[Dict[str, Any]] = None,
        validity_start: int = 0,
        validity_end: Optional[int] = None,
    ) -> None:
        """Emit RUNTIME_STATE_SNAPSHOT event."""
        self.emit({
            "kind": "RUNTIME_STATE_SNAPSHOT",
            "t": t,
            "timebase": self._timebase,
            "run_id": self._run_id,
            "rimgb_hash": rimgb_hash,
            "state_fields": state_fields or {},
            "validity_window": {
                "start_t": validity_start,
                "end_t": validity_end if validity_end is not None else t,
            },
        })
    
    def emit_device_event(
        self,
        t: int,
        code: str,
        detail: Optional[Dict[str, Any]] = None,
        level: str = "INFO",
        message: Optional[str] = None,
    ) -> None:
        """Emit DEVICE_EVENT."""
        event = {
            "kind": "DEVICE_EVENT",
            "t": t,
            "timebase": self._timebase,
            "run_id": self._run_id,
            "code": code,
            "level": level,
            "message": message or code,
        }
        if detail:
            event["detail"] = detail
        self.emit(event)
    
    def emit_measurement(
        self,
        t: int,
        detector_id: str,
        measurement_id: str,
        value_type: str,
        value_data: Any,
        op_id: Optional[str] = None,
    ) -> None:
        """Emit MEASUREMENT event."""
        event = {
            "kind": "MEASUREMENT",
            "t": t,
            "timebase": self._timebase,
            "run_id": self._run_id,
            "detector_id": detector_id,
            "measurement_id": measurement_id,
            "value": {
                "type": value_type,
                "data": value_data,
            },
        }
        if op_id:
            event["op_id"] = op_id
        self.emit(event)
    
    def emit_ecrp_attempt(
        self,
        t: int,
        attempt_index: int,
        strategy: str,
        outcome: str,
        deltas: Dict[str, Any],
        parameters: Dict[str, Any],
    ) -> None:
        """Emit ECRP_ATTEMPT event."""
        self.emit({
            "kind": "ECRP_ATTEMPT",
            "t": t,
            "timebase": self._timebase,
            "run_id": self._run_id,
            "attempt_index": attempt_index,
            "strategy": strategy,
            "outcome": outcome,
            "deltas": deltas,
            "parameters": parameters,
        })
    
    def emit_error(
        self,
        t: int,
        code: str,
        message: str,
        detail: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit error DEVICE_EVENT."""
        self.emit_device_event(
            t=t,
            code=code,
            message=message,
            detail=detail,
            level="ERROR",
        )


# =============================================================================
# Execution Engine
# =============================================================================

@dataclass
class ExecutionConfig:
    """Configuration for execution engine."""
    ecrp_enabled: bool = False
    ecrp_max_attempts: int = 3
    strict_timing: bool = False
    emit_frame_events: bool = True
    emit_observations: bool = True
    transient_fault_channels: tuple[int, ...] = ()
    ecrp_recover_transient_faults: bool = False


@dataclass
class ExecutionResult:
    """Result from executing a container."""
    success: bool
    tick: int
    frames_executed: int
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


class ExecutionEngine:
    """
    Executes Klein containers on a substrate.
    
    This is the main integration point between:
    - Container validation (SImgB, manifest)
    - Payload parsing (ops → frames)
    - Substrate execution (frame application)
    - HAIL event emission
    """
    
    def __init__(
        self,
        substrate: SubstrateDriver,
        emitter: HAILEmitter,
        config: Optional[ExecutionConfig] = None,
    ):
        self._substrate = substrate
        self._emitter = emitter
        self._config = config or ExecutionConfig()
        
        self._parser = PayloadParser(context_from_substrate(substrate))
        self._tick = 0
        
        # ECRP state
        self._ecrp_attempts = 0
        self._ecrp_strategies = ["NUDGE_PULSE", "VOLTAGE_BOOST", "FREQUENCY_SWEEP"]
        self._transient_fault_consumed = False
    
    @property
    def tick(self) -> int:
        return self._tick
    
    def validate_container(self, container: Container) -> List[ValidationError]:
        """
        Validate a container before execution.
        
        Checks:
        - Manifest completeness
        - SImgB hash matching (if substrate supports)
        - Payload structure
        """
        errors: List[ValidationError] = []
        
        # Validate manifest
        if not container.manifest:
            errors.append(ValidationError(
                code=KleinErrorCode.SCHEMA_VIOLATION,
                message="Container missing manifest",
            ))
            return errors
        
        # Validate SImgB if substrate is VirtualSubstrate
        if isinstance(self._substrate, VirtualSubstrate):
            simgb_data = container.simgb if hasattr(container, 'simgb') and container.simgb else {}
            if hasattr(container, 'dsb') and container.dsb:
                simgb_data = container.dsb  # Legacy field name
            
            if isinstance(simgb_data, dict):
                simgb_errors = self._substrate.validate_simgb(simgb_data)
                errors.extend(simgb_errors)
        
        return errors
    
    def execute_container(self, container: Container) -> ExecutionResult:
        """
        Execute a container.
        
        Steps:
        1. Validate container
        2. Emit startup events
        3. Parse payload to frames
        4. Execute frames with ECRP
        5. Emit shutdown events
        """
        # Validate
        errors = self.validate_container(container)
        if errors:
            for error in errors:
                self._emitter.emit_error(
                    t=self._tick,
                    code=error.code.value,
                    message=error.message,
                    detail=error.detail,
                )
            return ExecutionResult(
                success=False,
                tick=self._tick,
                frames_executed=0,
                errors=[e.message for e in errors],
            )
        
        # Emit startup
        rimgb_hash = compute_hash({
            "manifest": container.manifest.model_dump() if container.manifest else {},
            "tick": self._tick,
        })
        self._emitter.emit_runtime_state_snapshot(
            t=self._tick,
            rimgb_hash=rimgb_hash,
            state_fields={"status": "starting"},
        )
        self._emitter.emit_device_event(t=self._tick, code="INIT")
        
        # Parse payload
        payload = None
        if hasattr(container, 'payload') and container.payload:
            payload = container.payload
            # Handle Pydantic model
            if hasattr(payload, 'model_dump'):
                payload = payload.model_dump()
        
        if not payload:
            # No payload - just emit success
            self._emitter.emit_device_event(t=self._tick, code="NO_PAYLOAD")
            return ExecutionResult(
                success=True,
                tick=self._tick,
                frames_executed=0,
            )
        
        self._parser = PayloadParser(context_from_substrate(self._substrate))
        self._parser.reset()
        payload_errors = self._parser.validate_container_payload(payload)
        if payload_errors:
            for error in payload_errors:
                self._emitter.emit_error(
                    t=self._tick,
                    code=error.code.value,
                    message=error.message,
                    detail=error.detail,
                )
            return ExecutionResult(
                success=False,
                tick=self._tick,
                frames_executed=0,
                errors=[error.message for error in payload_errors],
            )

        try:
            sequence = self._parser.parse_container_payload(payload)
        except ValueError as exc:
            code = str(exc) or KleinErrorCode.PAYLOAD_MALFORMED.value
            self._emitter.emit_error(
                t=self._tick,
                code=code,
                message=f"Payload conversion failed: {code}",
            )
            return ExecutionResult(
                success=False,
                tick=self._tick,
                frames_executed=0,
                errors=[code],
            )

        if not sequence.frames:
            self._emitter.emit_device_event(
                t=self._tick,
                code="NO_PAYLOAD",
                detail={"source_kind": sequence.source_kind.value},
            )
        
        # Execute frames
        frames_executed = 0
        exec_errors: List[str] = []
        exec_warnings: List[str] = []
        
        for frame in sequence.frames:
            self._tick += 1
            
            # Apply frame, with an optional deterministic simulator-only transient fault.
            ack = self._apply_frame_with_transient_fault(frame)
            frames_executed += 1
            
            # Emit frame event
            if self._config.emit_frame_events:
                self._emitter.emit_device_event(
                    t=self._tick,
                    code="FRAME_APPLIED" if ack.ok else "FRAME_FAILED",
                    detail={
                        "seq": frame.seq,
                        "electrodes": list(frame.active_electrodes),
                        "duration_ms": frame.duration_ms,
                    },
                )
            
            # Handle failure
            if not ack.ok:
                fault = ack.faults[0] if ack.faults else None
                fault_msg = fault.message if fault else "Unknown failure"
                fault_code = "FRAME_FAILED"
                fault_detail: Dict[str, Any] = {}
                if fault:
                    fault_detail = dict(fault.detail or {})
                    fault_code = str(fault_detail.get("klein_error_code") or fault.code.value)
                
                # Try ECRP recovery
                if self._config.ecrp_enabled:
                    recovered, ecrp_error = self._attempt_ecrp(
                        fault_msg,
                        recoverable=bool(ack.detail.get("transient_recoverable")),
                    )
                    if recovered:
                        self._tick += 1
                        retry_ack = self._substrate.apply_frame(frame)
                        if self._config.emit_frame_events:
                            self._emitter.emit_device_event(
                                t=self._tick,
                                code="FRAME_APPLIED" if retry_ack.ok else "FRAME_FAILED",
                                detail={
                                    "seq": frame.seq,
                                    "electrodes": list(frame.active_electrodes),
                                    "duration_ms": frame.duration_ms,
                                    "recovery_retry": True,
                                    "recovery_attempt": self._ecrp_attempts,
                                },
                            )
                        if not retry_ack.ok:
                            recovered = False
                            retry_fault = retry_ack.faults[0] if retry_ack.faults else None
                            fault_msg = retry_fault.message if retry_fault else fault_msg
                            if retry_fault:
                                fault_detail = dict(retry_fault.detail or {})
                                fault_code = str(fault_detail.get("klein_error_code") or retry_fault.code.value)
                    if not recovered:
                        if ecrp_error:
                            exec_errors.append(ecrp_error)
                        else:
                            exec_errors.append(fault_msg)
                        # The terminal fault evidence is emitted after the
                        # bounded ECRP attempt so causal evidence assertions can
                        # distinguish frame failure, attempted repair, and final
                        # unrecovered substrate fault.
                        self._tick += 1
                        self._emitter.emit_error(
                            t=self._tick,
                            code=fault_code,
                            message=fault_msg,
                            detail=fault_detail,
                        )
                        break
                else:
                    exec_errors.append(fault_msg)
                    self._emitter.emit_error(
                        t=self._tick,
                        code=fault_code,
                        message=fault_msg,
                        detail=fault_detail,
                    )
                    break
            
            # Check for warnings (e.g., stuck droplet)
            if ack.detail and ack.detail.get("warning"):
                exec_warnings.append(ack.detail.get("warning", ""))
            
            # Emit observations
            if self._config.emit_observations:
                observations = self._substrate.read_observations(since_seq=frame.seq - 1)
                for obs in observations:
                    if obs.seq == frame.seq:
                        self._emitter.emit_measurement(
                            t=self._tick,
                            detector_id=obs.source.value,
                            measurement_id=f"obs_{obs.seq}",
                            value_type="F64" if isinstance(obs.signals.get("impedance_ohms"), float) else "BOOL",
                            value_data=obs.signals,
                        )
        
        # Emit shutdown
        self._tick += 1
        self._emitter.emit_runtime_state_snapshot(
            t=self._tick,
            rimgb_hash=rimgb_hash,
            state_fields={"status": "completed"},
            validity_end=self._tick,
        )
        self._emitter.emit_device_event(
            t=self._tick,
            code="SHUTDOWN",
            detail={"frames_executed": frames_executed},
        )
        
        return ExecutionResult(
            success=len(exec_errors) == 0,
            tick=self._tick,
            frames_executed=frames_executed,
            errors=exec_errors,
            warnings=exec_warnings,
        )
    
    def _apply_frame_with_transient_fault(self, frame: Frame) -> Ack:
        if (
            self._config.ecrp_recover_transient_faults
            and not self._transient_fault_consumed
            and set(frame.active_electrodes).intersection(self._config.transient_fault_channels)
        ):
            self._transient_fault_consumed = True
            channel = sorted(set(frame.active_electrodes).intersection(self._config.transient_fault_channels))[0]
            return Ack(
                seq=frame.seq,
                ok=False,
                faults=(
                    Fault(
                        code=FaultCode.CHANNEL_UNAVAILABLE,
                        message=f"Transient simulated channel failure on electrode {channel}",
                        detail={
                            "electrode_id": channel,
                            "klein_error_code": "FRAME_FAILED",
                            "transient_recoverable": True,
                        },
                    ),
                ),
                detail={"transient_recoverable": True, "electrode_id": channel},
            )
        return self._substrate.apply_frame(frame)

    def _attempt_ecrp(self, fault_description: str, *, recoverable: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Attempt ECRP recovery.
        
        Returns:
            (recovered, error_message) - error_message is set if max_attempts exceeded
        """
        if self._ecrp_attempts >= self._config.ecrp_max_attempts:
            self._emitter.emit_error(
                t=self._tick,
                code=KleinErrorCode.ECRP_BOUNDS_EXCEEDED.value,
                message=f"ECRP exceeded max_attempts={self._config.ecrp_max_attempts}",
            )
            return False, KleinErrorCode.ECRP_BOUNDS_EXCEEDED.value
        
        self._ecrp_attempts += 1
        strategy = self._ecrp_strategies[(self._ecrp_attempts - 1) % len(self._ecrp_strategies)]
        
        outcome = "SUCCESS" if recoverable else ("NO_CHANGE" if self._ecrp_attempts < self._config.ecrp_max_attempts else "PARTIAL")
        
        self._emitter.emit_ecrp_attempt(
            t=self._tick,
            attempt_index=self._ecrp_attempts,
            strategy=strategy,
            outcome=outcome,
            deltas={"occupancy_shift_cells": 0 if outcome == "NO_CHANGE" else 1},
            parameters={"strategy": strategy, "attempt": self._ecrp_attempts},
        )
        
        return recoverable, None
    
    def execute_frames(self, frames: List[Frame]) -> ExecutionResult:
        """
        Execute a list of frames directly (for simple cases).
        
        This bypasses container validation and payload parsing.
        """
        frames_executed = 0
        errors: List[str] = []
        
        self._emitter.emit_device_event(t=self._tick, code="FRAMES_START")
        
        for frame in frames:
            self._tick += 1
            ack = self._substrate.apply_frame(frame)
            frames_executed += 1
            
            if self._config.emit_frame_events:
                self._emitter.emit_device_event(
                    t=self._tick,
                    code="FRAME_APPLIED" if ack.ok else "FRAME_FAILED",
                    detail={"seq": frame.seq},
                )
            
            if not ack.ok:
                fault = ack.faults[0] if ack.faults else None
                errors.append(fault.message if fault else "Frame failed")
                break
        
        self._tick += 1
        self._emitter.emit_device_event(
            t=self._tick,
            code="FRAMES_END",
            detail={"frames_executed": frames_executed},
        )
        
        return ExecutionResult(
            success=len(errors) == 0,
            tick=self._tick,
            frames_executed=frames_executed,
            errors=errors,
        )

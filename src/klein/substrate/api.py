from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple, Union


# ----------------------------
# Error / fault model
# ----------------------------

class FaultCode(str, Enum):
    OVERRIDE = "E_OVERRIDE"                 # generic driver override
    OVERCURRENT = "E_OVERCURRENT"
    UNDERVOLTAGE = "E_UNDERVOLTAGE"
    FRAME_TOO_FAST = "E_FRAME_TOO_FAST"
    CHANNEL_UNAVAILABLE = "E_CHANNEL_UNAVAILABLE"
    CARTRIDGE_MISMATCH = "E_CARTRIDGE_MISMATCH"
    SENSE_UNAVAILABLE = "E_SENSE_UNAVAILABLE"
    EXECUTION_ABORTED = "E_EXECUTION_ABORTED"
    ESTOP = "E_ESTOP"                       # watchdog timeout (Dead Man's Switch)
    UNKNOWN = "E_UNKNOWN"


@dataclass(frozen=True)
class Fault:
    code: FaultCode
    message: str
    detail: Dict[str, Any] = field(default_factory=dict)


class SubstrateError(RuntimeError):
    def __init__(self, fault: Fault):
        super().__init__(f"{fault.code}: {fault.message}")
        self.fault = fault


# ----------------------------
# Capability / topology / waveform
# ----------------------------

class AddressingMode(str, Enum):
    DIRECT = "direct"           # electrode IDs addressable directly
    MATRIX = "matrix"           # row/col multiplexing
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class VoltageRange:
    v_min: float
    v_max: float


@dataclass(frozen=True)
class FrequencyRange:
    hz_min: float
    hz_max: float


class WaveformMode(str, Enum):
    DC = "DC"
    AC = "AC"


@dataclass(frozen=True)
class WaveformProfile:
    mode: WaveformMode
    voltage_v: float
    ac_frequency_hz: Optional[float] = None
    # You can extend with duty cycle, phase, ramp, etc.


@dataclass(frozen=True)
class TimingProfile:
    min_frame_ms: int
    typical_jitter_ms: int = 0
    max_schedule_horizon_ms: Optional[int] = None  # Watchdog timeout (Dead Man's Switch)


@dataclass(frozen=True)
class SensingProfile:
    impedance: bool = False
    vision: bool = False
    electrode_feedback: bool = False


@dataclass(frozen=True)
class CapabilityProfile:
    device_vendor: str
    device_model: str
    firmware: str

    max_channels: int
    addressing: AddressingMode
    supports_groups: bool

    waveforms: Tuple[WaveformMode, ...]
    voltage_range: VoltageRange
    ac_frequency_range: Optional[FrequencyRange]

    timing: TimingProfile
    sensing: SensingProfile

    safety_estop: bool = True
    safety_overcurrent_protection: bool = False


@dataclass(frozen=True)
class Electrode:
    eid: int
    label: Optional[str] = None
    # Optional geometric metadata for vision mapping:
    x: Optional[float] = None
    y: Optional[float] = None


@dataclass(frozen=True)
class ElectrodeTopology:
    electrodes: Tuple[Electrode, ...]
    adjacency: Mapping[int, Tuple[int, ...]]  # eid -> neighboring eids
    cartridge_id: Optional[str] = None
    # You can store a grid size, geometry file ref, etc.


# ----------------------------
# Frame / observation
# ----------------------------

@dataclass(frozen=True)
class Frame:
    seq: int
    active_electrodes: Tuple[int, ...]
    duration_ms: int
    wf_override: Optional[WaveformProfile] = None
    tags: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Ack:
    seq: int
    ok: bool
    faults: Tuple[Fault, ...] = ()
    detail: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RunOptions:
    # Keep it small. Extend later for streaming, chunk size, timing strictness, etc.
    strict_timing: bool = False
    allow_partial: bool = True


@dataclass(frozen=True)
class RunReport:
    ok: bool
    last_seq: int
    acks: Tuple[Ack, ...]
    faults: Tuple[Fault, ...] = ()
    detail: Dict[str, Any] = field(default_factory=dict)


class ObservationSource(str, Enum):
    NONE = "none"
    CONTROLLER = "controller"
    VISION = "vision"
    IMPEDANCE = "impedance"


@dataclass(frozen=True)
class Observation:
    seq: int
    time_ms: int
    source: ObservationSource
    signals: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HealthReport:
    ok: bool
    flags: Tuple[str, ...] = ()
    detail: Dict[str, Any] = field(default_factory=dict)


# ----------------------------
# Driver boundary
# ----------------------------

class SubstrateDriver(Protocol):
    """
    The Klein "Linux driver" boundary.
    Everything reduces to sequences of Frames + optional Observations.
    """

    def connect(self, uri: str) -> None:
        ...

    def get_capabilities(self) -> CapabilityProfile:
        ...

    def get_topology(self) -> ElectrodeTopology:
        ...

    def set_waveform(self, wf: WaveformProfile) -> None:
        ...

    def apply_frame(self, frame: Frame) -> Ack:
        ...

    def run_sequence(self, frames: Sequence[Frame], options: Optional[RunOptions] = None) -> RunReport:
        ...

    def read_observations(self, since_seq: Optional[int] = None) -> List[Observation]:
        ...

    def get_health(self) -> HealthReport:
        ...

    def estop(self) -> None:
        ...

    def reset(self) -> None:
        ...


# ----------------------------
# Deterministic Mock Substrate
# ----------------------------

@dataclass
class FaultRule:
    """
    Deterministic, programmable fault injection.
    Rules are evaluated in order.
    """
    when_seq: Optional[int] = None
    when_contains_electrode: Optional[int] = None
    fault: Fault = field(default_factory=lambda: Fault(FaultCode.UNKNOWN, "Injected fault"))
    once: bool = True
    _fired: bool = False


class MockSubstrate(SubstrateDriver):
    def __init__(
        self,
        max_channels: int = 128,
        topology: Optional[ElectrodeTopology] = None,
        capabilities: Optional[CapabilityProfile] = None,
        timing: TimingProfile = TimingProfile(min_frame_ms=5, typical_jitter_ms=1),
    ):
        self._connected = False
        self._uri = None

        if topology is None:
            electrodes = tuple(Electrode(eid=i) for i in range(max_channels))
            # Default: linear adjacency (you can swap for grid)
            adjacency = {i: tuple(j for j in (i - 1, i + 1) if 0 <= j < max_channels) for i in range(max_channels)}
            topology = ElectrodeTopology(electrodes=electrodes, adjacency=adjacency, cartridge_id="MOCK-CARTRIDGE")

        if capabilities is None:
            capabilities = CapabilityProfile(
                device_vendor="mock",
                device_model="MockSubstrate",
                firmware="0.0.1",
                max_channels=max_channels,
                addressing=AddressingMode.DIRECT,
                supports_groups=True,
                waveforms=(WaveformMode.DC, WaveformMode.AC),
                voltage_range=VoltageRange(v_min=0.0, v_max=300.0),
                ac_frequency_range=FrequencyRange(hz_min=1.0, hz_max=50_000.0),
                timing=timing,
                sensing=SensingProfile(impedance=False, vision=False, electrode_feedback=False),
                safety_estop=True,
                safety_overcurrent_protection=True,
            )

        self._topology = topology
        self._cap = capabilities
        self._wf = WaveformProfile(mode=WaveformMode.DC, voltage_v=0.0, ac_frequency_hz=None)
        self._estopped = False
        self._time_ms = 0
        self._fault_rules: List[FaultRule] = []
        self._last_seq_applied: Optional[int] = None
        self._observations: List[Observation] = []
        self._last_frame_time: Optional[float] = None  # Watchdog timer (wall-clock)

    # --- Control plane ---

    def connect(self, uri: str) -> None:
        self._connected = True
        self._uri = uri
        self._last_frame_time = None  # Reset watchdog on connect

    def get_capabilities(self) -> CapabilityProfile:
        self._require_ready()
        return self._cap

    def get_topology(self) -> ElectrodeTopology:
        self._require_ready()
        return self._topology

    def set_waveform(self, wf: WaveformProfile) -> None:
        self._require_ready()
        self._validate_waveform(wf)
        self._wf = wf

    def get_health(self) -> HealthReport:
        self._require_connected()
        flags: List[str] = []
        if self._estopped:
            flags.append("ESTOPPED")
        return HealthReport(ok=not self._estopped, flags=tuple(flags), detail={"uri": self._uri})

    def estop(self) -> None:
        self._require_connected()
        self._estopped = True

    def reset(self) -> None:
        self._require_connected()
        self._estopped = False
        self._time_ms = 0
        self._last_seq_applied = None
        self._observations.clear()
        self._last_frame_time = None  # Reset watchdog

    # --- Data plane (frames) ---

    def apply_frame(self, frame: Frame) -> Ack:
        self._require_ready()
        if self._estopped:
            return Ack(seq=frame.seq, ok=False, faults=(Fault(FaultCode.EXECUTION_ABORTED, "E-stop active"),))

        # Watchdog check: max_schedule_horizon_ms (Dead Man's Switch)
        now = time.monotonic()
        horizon_ms = self._cap.timing.max_schedule_horizon_ms
        if horizon_ms is not None and self._last_frame_time is not None:
            elapsed_ms = (now - self._last_frame_time) * 1000
            if elapsed_ms > horizon_ms:
                self._estopped = True
                return Ack(
                    seq=frame.seq,
                    ok=False,
                    faults=(Fault(FaultCode.ESTOP, "Watchdog timeout: max_schedule_horizon_ms exceeded", {"elapsed_ms": elapsed_ms, "horizon_ms": horizon_ms}),),
                )
        self._last_frame_time = now

        # timing constraints
        if frame.duration_ms < self._cap.timing.min_frame_ms:
            f = Fault(FaultCode.FRAME_TOO_FAST, "Frame duration below device minimum", {"min_frame_ms": self._cap.timing.min_frame_ms})
            return Ack(seq=frame.seq, ok=False, faults=(f,))

        # electrode validity
        for eid in frame.active_electrodes:
            if eid < 0 or eid >= self._cap.max_channels:
                f = Fault(FaultCode.CHANNEL_UNAVAILABLE, "Electrode out of range", {"eid": eid, "max": self._cap.max_channels})
                return Ack(seq=frame.seq, ok=False, faults=(f,))

        # injected fault?
        injected = self._maybe_inject_fault(frame)
        if injected is not None:
            return Ack(seq=frame.seq, ok=False, faults=(injected,))

        # apply
        self._time_ms += frame.duration_ms
        self._last_seq_applied = frame.seq

        # v1: no real observations, but we keep the pipe alive
        self._observations.append(
            Observation(
                seq=frame.seq,
                time_ms=self._time_ms,
                source=ObservationSource.NONE,
                signals={"active_electrodes": list(frame.active_electrodes), "wf": self._wf.mode.value},
            )
        )
        return Ack(seq=frame.seq, ok=True, faults=(), detail={"time_ms": self._time_ms})

    def run_sequence(self, frames: Sequence[Frame], options: Optional[RunOptions] = None) -> RunReport:
        self._require_ready()
        opts = options or RunOptions()
        acks: List[Ack] = []
        faults: List[Fault] = []

        for fr in frames:
            ack = self.apply_frame(fr)
            acks.append(ack)
            if not ack.ok:
                faults.extend(list(ack.faults))
                if not opts.allow_partial:
                    return RunReport(ok=False, last_seq=fr.seq, acks=tuple(acks), faults=tuple(faults))

        ok = all(a.ok for a in acks)
        last_seq = frames[-1].seq if frames else (self._last_seq_applied or 0)
        return RunReport(ok=ok, last_seq=last_seq, acks=tuple(acks), faults=tuple(faults))

    def read_observations(self, since_seq: Optional[int] = None) -> List[Observation]:
        self._require_ready()
        if since_seq is None:
            return list(self._observations)
        return [o for o in self._observations if o.seq > since_seq]

    # --- Fault injection API (test-only) ---

    def add_fault_rule(self, rule: FaultRule) -> None:
        """Add a deterministic fault rule for CI tests."""
        self._fault_rules.append(rule)

    # --- Internal helpers ---

    def _require_connected(self) -> None:
        if not self._connected:
            raise SubstrateError(Fault(FaultCode.UNKNOWN, "Not connected"))

    def _require_ready(self) -> None:
        self._require_connected()
        # extend later: cartridge validation, safety checks, etc.

    def _validate_waveform(self, wf: WaveformProfile) -> None:
        if wf.mode not in self._cap.waveforms:
            raise SubstrateError(Fault(FaultCode.UNKNOWN, "Waveform mode not supported", {"mode": wf.mode.value}))
        if not (self._cap.voltage_range.v_min <= wf.voltage_v <= self._cap.voltage_range.v_max):
            raise SubstrateError(Fault(FaultCode.UNDERVOLTAGE, "Voltage out of range", {"voltage_v": wf.voltage_v}))
        if wf.mode == WaveformMode.AC:
            if wf.ac_frequency_hz is None:
                raise SubstrateError(Fault(FaultCode.UNKNOWN, "AC mode requires ac_frequency_hz"))
            fr = self._cap.ac_frequency_range
            if fr and not (fr.hz_min <= wf.ac_frequency_hz <= fr.hz_max):
                raise SubstrateError(Fault(FaultCode.UNKNOWN, "AC frequency out of range", {"hz": wf.ac_frequency_hz}))

    def _maybe_inject_fault(self, frame: Frame) -> Optional[Fault]:
        for rule in self._fault_rules:
            if rule.once and rule._fired:
                continue
            if rule.when_seq is not None and frame.seq != rule.when_seq:
                continue
            if rule.when_contains_electrode is not None and rule.when_contains_electrode not in frame.active_electrodes:
                continue
            rule._fired = True
            return rule.fault
        return None


# ----------------------------
# OpenDrop driver stub 
# ----------------------------

class OpenDropDriverStub(SubstrateDriver):
    """
    Placeholder driver that:
      - reports realistic-ish capabilities/topology
      - validates inputs
      - does NOT actually drive hardware

    You can later replace internals with real OpenDrop communication.
    """
    def __init__(self, channels: int = 128):
        self._connected = False
        self._uri = None

        electrodes = tuple(Electrode(eid=i) for i in range(channels))
        adjacency = {i: tuple(j for j in (i - 1, i + 1) if 0 <= j < channels) for i in range(channels)}
        self._topology = ElectrodeTopology(electrodes=electrodes, adjacency=adjacency, cartridge_id="OPENDROP-STUB")

        self._cap = CapabilityProfile(
            device_vendor="GaudiLabs",
            device_model="OpenDrop-like",
            firmware="unknown",
            max_channels=channels,
            addressing=AddressingMode.DIRECT,
            supports_groups=True,
            waveforms=(WaveformMode.DC, WaveformMode.AC),
            voltage_range=VoltageRange(v_min=160.0, v_max=300.0),  # from OpenDrop V4 description 
            ac_frequency_range=FrequencyRange(hz_min=1.0, hz_max=50_000.0),
            timing=TimingProfile(min_frame_ms=5, typical_jitter_ms=2),
            sensing=SensingProfile(impedance=False, vision=False, electrode_feedback=False),
            safety_estop=True,
            safety_overcurrent_protection=True,
        )

        self._wf = WaveformProfile(mode=WaveformMode.DC, voltage_v=160.0)
        self._estopped = False
        self._time_ms = 0
        self._observations: List[Observation] = []
        self._last_frame_time: Optional[float] = None  # Watchdog timer (wall-clock)

    def connect(self, uri: str) -> None:
        self._connected = True
        self._uri = uri
        self._last_frame_time = None  # Reset watchdog on connect

    def get_capabilities(self) -> CapabilityProfile:
        self._require_ready()
        return self._cap

    def get_topology(self) -> ElectrodeTopology:
        self._require_ready()
        return self._topology

    def set_waveform(self, wf: WaveformProfile) -> None:
        self._require_ready()
        # reuse MockSubstrate validation logic idea
        if wf.mode not in self._cap.waveforms:
            raise SubstrateError(Fault(FaultCode.UNKNOWN, "Waveform mode not supported", {"mode": wf.mode.value}))
        if not (self._cap.voltage_range.v_min <= wf.voltage_v <= self._cap.voltage_range.v_max):
            raise SubstrateError(Fault(FaultCode.UNDERVOLTAGE, "Voltage out of range", {"voltage_v": wf.voltage_v}))
        self._wf = wf

    def apply_frame(self, frame: Frame) -> Ack:
        self._require_ready()
        if self._estopped:
            return Ack(seq=frame.seq, ok=False, faults=(Fault(FaultCode.EXECUTION_ABORTED, "E-stop active"),))

        # Watchdog check: max_schedule_horizon_ms (Dead Man's Switch)
        now = time.monotonic()
        horizon_ms = self._cap.timing.max_schedule_horizon_ms
        if horizon_ms is not None and self._last_frame_time is not None:
            elapsed_ms = (now - self._last_frame_time) * 1000
            if elapsed_ms > horizon_ms:
                self._estopped = True
                return Ack(
                    seq=frame.seq,
                    ok=False,
                    faults=(Fault(FaultCode.ESTOP, "Watchdog timeout: max_schedule_horizon_ms exceeded", {"elapsed_ms": elapsed_ms, "horizon_ms": horizon_ms}),),
                )
        self._last_frame_time = now

        if frame.duration_ms < self._cap.timing.min_frame_ms:
            f = Fault(FaultCode.FRAME_TOO_FAST, "Frame duration below device minimum", {"min_frame_ms": self._cap.timing.min_frame_ms})
            return Ack(seq=frame.seq, ok=False, faults=(f,))
        for eid in frame.active_electrodes:
            if eid < 0 or eid >= self._cap.max_channels:
                f = Fault(FaultCode.CHANNEL_UNAVAILABLE, "Electrode out of range", {"eid": eid, "max": self._cap.max_channels})
                return Ack(seq=frame.seq, ok=False, faults=(f,))

        # no-op "execution"
        self._time_ms += frame.duration_ms
        self._observations.append(
            Observation(seq=frame.seq, time_ms=self._time_ms, source=ObservationSource.NONE, signals={"stub": True})
        )
        return Ack(seq=frame.seq, ok=True, faults=(), detail={"time_ms": self._time_ms, "stub": True})

    def run_sequence(self, frames: Sequence[Frame], options: Optional[RunOptions] = None) -> RunReport:
        self._require_ready()
        acks: List[Ack] = []
        faults: List[Fault] = []
        opts = options or RunOptions()

        for fr in frames:
            ack = self.apply_frame(fr)
            acks.append(ack)
            if not ack.ok:
                faults.extend(list(ack.faults))
                if not opts.allow_partial:
                    return RunReport(ok=False, last_seq=fr.seq, acks=tuple(acks), faults=tuple(faults))

        ok = all(a.ok for a in acks)
        last_seq = frames[-1].seq if frames else 0
        return RunReport(ok=ok, last_seq=last_seq, acks=tuple(acks), faults=tuple(faults), detail={"stub": True})

    def read_observations(self, since_seq: Optional[int] = None) -> List[Observation]:
        self._require_ready()
        if since_seq is None:
            return list(self._observations)
        return [o for o in self._observations if o.seq > since_seq]

    def get_health(self) -> HealthReport:
        self._require_connected()
        flags: List[str] = []
        if self._estopped:
            flags.append("ESTOPPED")
        return HealthReport(ok=not self._estopped, flags=tuple(flags), detail={"uri": self._uri, "stub": True})

    def estop(self) -> None:
        self._require_connected()
        self._estopped = True

    def reset(self) -> None:
        self._require_connected()
        self._estopped = False
        self._time_ms = 0
        self._observations.clear()
        self._last_frame_time = None  # Reset watchdog

    def _require_connected(self) -> None:
        if not self._connected:
            raise SubstrateError(Fault(FaultCode.UNKNOWN, "Not connected"))

    def _require_ready(self) -> None:
        self._require_connected()

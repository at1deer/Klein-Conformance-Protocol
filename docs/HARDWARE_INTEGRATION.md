# Hardware Integration Guide

> Public-alpha note: this is historical/target guidance for future hardware driver work. The
> current repository does not implement hardware IO, HIL execution, OpenDrop hardware control,
> physical truth proof, trusted timestamps, or hardware attestation. For the current adapter
> boundary, read `docs/ADAPTERS.md`.

> OpenDrop note: KCP does not copy or vendor GaudiLabs/OpenDrop firmware or controller code. Future
> hardware integration requires explicit license compatibility review before copying or deriving from
> GPL-licensed code.

This guide preserves future hardware-driver design notes. It is not current-alpha implementation
guidance. Future hardware work would replace dry-run stubs with a real driver behind an explicit
hardware gate and release claim review.

---

## Overview

Klein uses a **Protocol-based driver interface** (`SubstrateDriver`) that abstracts hardware differences. Your driver must implement this protocol to be conformance-testable.

The existing `MockSubstrate` and `OpenDropDriverStub` in `src/klein/substrate/api.py` provide reference implementations.

---

## 1. The SubstrateDriver Protocol

Location: `src/klein/substrate/api.py`

```python
class SubstrateDriver(Protocol):
    """
    The Klein "Linux driver" boundary.
    Everything reduces to sequences of Frames + optional Observations.
    """

    def connect(self, uri: str) -> None:
        """Establish connection to hardware."""
        ...

    def get_capabilities(self) -> CapabilityProfile:
        """Return hardware capabilities for negotiation."""
        ...

    def get_topology(self) -> ElectrodeTopology:
        """Return electrode layout and adjacency graph."""
        ...

    def set_waveform(self, wf: WaveformProfile) -> None:
        """Configure actuation waveform (DC/AC, voltage, frequency)."""
        ...

    def apply_frame(self, frame: Frame) -> Ack:
        """Apply a single actuation frame, return acknowledgment."""
        ...

    def run_sequence(self, frames: Sequence[Frame], options: RunOptions) -> RunReport:
        """Execute a sequence of frames."""
        ...

    def read_observations(self, since_seq: int | None) -> List[Observation]:
        """Read sensor observations since a given sequence number."""
        ...

    def get_health(self) -> HealthReport:
        """Return current hardware health status."""
        ...

    def estop(self) -> None:
        """Emergency stop - immediately disable all electrodes."""
        ...

    def reset(self) -> None:
        """Reset hardware state after estop or error."""
        ...
```

---

## 2. Required Data Types

### CapabilityProfile

Your driver must report a `CapabilityProfile` with at minimum:

```python
from klein.substrate.api import (
    CapabilityProfile,
    AddressingMode,
    WaveformMode,
    VoltageRange,
    FrequencyRange,
    TimingProfile,
    SensingProfile,
)

capabilities = CapabilityProfile(
    device_vendor="YourCompany",
    device_model="YourModel_V1",
    firmware="1.0.0",
    max_channels=128,
    addressing=AddressingMode.DIRECT,
    supports_groups=True,
    waveforms=(WaveformMode.AC, WaveformMode.DC),
    voltage_range=VoltageRange(v_min=100.0, v_max=300.0),
    ac_frequency_range=FrequencyRange(hz_min=1.0, hz_max=50000.0),
    timing=TimingProfile(
        min_frame_ms=5,              # Fastest frame rate
        typical_jitter_ms=2,
        max_schedule_horizon_ms=1000, # Watchdog timeout (REQUIRED)
    ),
    sensing=SensingProfile(
        impedance=False,
        vision=False,
        electrode_feedback=False,
    ),
    safety_estop=True,
    safety_overcurrent_protection=True,
)
```

### Frame and Ack

```python
from klein.substrate.api import Frame, Ack, Fault, FaultCode

# A frame is a single actuation command
frame = Frame(
    seq=1,                         # Sequence number (monotonic)
    active_electrodes=(17, 18, 19), # Electrodes to activate
    duration_ms=20,                # How long to hold
    wf_override=None,              # Optional per-frame waveform
)

# Acknowledge success
ack = Ack(seq=1, ok=True, faults=())

# Acknowledge failure
ack = Ack(
    seq=1,
    ok=False,
    faults=(Fault(FaultCode.CHANNEL_UNAVAILABLE, "Electrode 17 stuck"),),
)
```

### ElectrodeTopology

```python
from klein.substrate.api import Electrode, ElectrodeTopology

electrodes = tuple(
    Electrode(eid=i, label=f"E{i}", x=i*100, y=0)
    for i in range(128)
)

# Adjacency: which electrodes neighbor which
adjacency = {
    0: (1,),
    1: (0, 2),
    2: (1, 3),
    # ...
}

topology = ElectrodeTopology(
    electrodes=electrodes,
    adjacency=adjacency,
    cartridge_id="OPENDROP-V4-128",
)
```

---

## 3. Future Driver Sketch - Not Current Alpha

The following OpenDrop-style serial example is illustrative pseudocode only. It is not implemented in
current alpha, is not tested against hardware, and is not part of the 1.0.0a0 support claim.

### Example: OpenDrop Serial Driver Sketch

```python
import serial
import time
from typing import List, Optional, Sequence

from klein.substrate.api import (
    SubstrateDriver,
    CapabilityProfile,
    ElectrodeTopology,
    Electrode,
    WaveformProfile,
    WaveformMode,
    VoltageRange,
    FrequencyRange,
    TimingProfile,
    SensingProfile,
    AddressingMode,
    Frame,
    Ack,
    Fault,
    FaultCode,
    RunOptions,
    RunReport,
    Observation,
    ObservationSource,
    HealthReport,
    SubstrateError,
)


class OpenDropDriver(SubstrateDriver):
    """
    Future OpenDrop V4 serial driver sketch.
    
    URI format: "serial:///dev/ttyUSB0:115200"
    """
    
    def __init__(self, channels: int = 128):
        self._connected = False
        self._serial: Optional[serial.Serial] = None
        self._channels = channels
        self._estopped = False
        self._time_ms = 0
        self._last_seq = 0
        self._observations: List[Observation] = []
        self._last_frame_time: Optional[float] = None
        
        # Build topology
        electrodes = tuple(Electrode(eid=i) for i in range(channels))
        # OpenDrop V4 has an 8x16 grid layout
        adjacency = self._build_grid_adjacency(8, 16)
        self._topology = ElectrodeTopology(
            electrodes=electrodes,
            adjacency=adjacency,
            cartridge_id="OPENDROP-V4",
        )
        
        # Capabilities
        self._cap = CapabilityProfile(
            device_vendor="GaudiLabs",
            device_model="OpenDrop_V4",
            firmware="unknown",  # Will be updated on connect
            max_channels=channels,
            addressing=AddressingMode.DIRECT,
            supports_groups=True,
            waveforms=(WaveformMode.AC,),  # OpenDrop is typically AC
            voltage_range=VoltageRange(v_min=160.0, v_max=300.0),
            ac_frequency_range=FrequencyRange(hz_min=100.0, hz_max=10000.0),
            timing=TimingProfile(
                min_frame_ms=10,
                typical_jitter_ms=5,
                max_schedule_horizon_ms=1000,  # 1 second watchdog
            ),
            sensing=SensingProfile(impedance=False, vision=False, electrode_feedback=False),
            safety_estop=True,
            safety_overcurrent_protection=True,
        )
        
        self._wf = WaveformProfile(mode=WaveformMode.AC, voltage_v=200.0, ac_frequency_hz=1000.0)
    
    def _build_grid_adjacency(self, rows: int, cols: int) -> dict:
        """Build adjacency map for a grid topology."""
        adjacency = {}
        for r in range(rows):
            for c in range(cols):
                eid = r * cols + c
                neighbors = []
                if r > 0: neighbors.append((r-1) * cols + c)  # Up
                if r < rows-1: neighbors.append((r+1) * cols + c)  # Down
                if c > 0: neighbors.append(r * cols + (c-1))  # Left
                if c < cols-1: neighbors.append(r * cols + (c+1))  # Right
                adjacency[eid] = tuple(neighbors)
        return adjacency
    
    def connect(self, uri: str) -> None:
        """
        Connect to OpenDrop via serial.
        
        URI format: serial:///dev/ttyUSB0:115200
        """
        if not uri.startswith("serial://"):
            raise SubstrateError(Fault(FaultCode.UNKNOWN, f"Invalid URI scheme: {uri}"))
        
        # Parse URI: serial:///dev/ttyUSB0:115200
        path = uri[len("serial://"):]
        if ":" in path:
            port, baud_str = path.rsplit(":", 1)
            baud = int(baud_str)
        else:
            port = path
            baud = 115200
        
        try:
            self._serial = serial.Serial(port, baud, timeout=1.0)
            time.sleep(2)  # Wait for Arduino reset
            
            # Query firmware version
            self._serial.write(b"VERSION\n")
            response = self._serial.readline().decode().strip()
            if response:
                # Update firmware in capabilities (would need mutable version)
                pass
            
            self._connected = True
            self._last_frame_time = None
            
        except serial.SerialException as e:
            raise SubstrateError(Fault(FaultCode.UNKNOWN, f"Serial connection failed: {e}"))
    
    def get_capabilities(self) -> CapabilityProfile:
        self._require_connected()
        return self._cap
    
    def get_topology(self) -> ElectrodeTopology:
        self._require_connected()
        return self._topology
    
    def set_waveform(self, wf: WaveformProfile) -> None:
        self._require_connected()
        
        # Validate
        if wf.mode not in self._cap.waveforms:
            raise SubstrateError(Fault(FaultCode.UNKNOWN, f"Unsupported waveform mode: {wf.mode}"))
        if not (self._cap.voltage_range.v_min <= wf.voltage_v <= self._cap.voltage_range.v_max):
            raise SubstrateError(Fault(FaultCode.UNDERVOLTAGE, f"Voltage out of range: {wf.voltage_v}V"))
        
        # Send to hardware
        if self._serial:
            cmd = f"VOLTAGE {int(wf.voltage_v)}\n"
            self._serial.write(cmd.encode())
            self._serial.readline()  # Consume ACK
            
            if wf.ac_frequency_hz:
                cmd = f"FREQ {int(wf.ac_frequency_hz)}\n"
                self._serial.write(cmd.encode())
                self._serial.readline()
        
        self._wf = wf
    
    def apply_frame(self, frame: Frame) -> Ack:
        self._require_connected()
        
        if self._estopped:
            return Ack(seq=frame.seq, ok=False, 
                       faults=(Fault(FaultCode.EXECUTION_ABORTED, "E-stop active"),))
        
        # Watchdog check
        now = time.monotonic()
        horizon_ms = self._cap.timing.max_schedule_horizon_ms
        if horizon_ms and self._last_frame_time is not None:
            elapsed_ms = (now - self._last_frame_time) * 1000
            if elapsed_ms > horizon_ms:
                self._estopped = True
                return Ack(seq=frame.seq, ok=False,
                           faults=(Fault(FaultCode.ESTOP, "Watchdog timeout"),))
        self._last_frame_time = now
        
        # Validate frame
        if frame.duration_ms < self._cap.timing.min_frame_ms:
            return Ack(seq=frame.seq, ok=False,
                       faults=(Fault(FaultCode.FRAME_TOO_FAST, "Frame too fast"),))
        
        for eid in frame.active_electrodes:
            if eid < 0 or eid >= self._cap.max_channels:
                return Ack(seq=frame.seq, ok=False,
                           faults=(Fault(FaultCode.CHANNEL_UNAVAILABLE, f"Invalid electrode: {eid}"),))
        
        # Send to hardware
        if self._serial:
            # Format: SET <electrode_list>
            electrode_str = ",".join(map(str, frame.active_electrodes))
            cmd = f"SET {electrode_str}\n"
            self._serial.write(cmd.encode())
            
            # Wait for acknowledgment
            response = self._serial.readline().decode().strip()
            if response != "OK":
                return Ack(seq=frame.seq, ok=False,
                           faults=(Fault(FaultCode.UNKNOWN, f"Hardware error: {response}"),))
            
            # Hold for duration
            time.sleep(frame.duration_ms / 1000.0)
        
        self._time_ms += frame.duration_ms
        self._last_seq = frame.seq
        
        # Record observation
        self._observations.append(Observation(
            seq=frame.seq,
            time_ms=self._time_ms,
            source=ObservationSource.CONTROLLER,
            signals={"active_electrodes": list(frame.active_electrodes)},
        ))
        
        return Ack(seq=frame.seq, ok=True)
    
    def run_sequence(self, frames: Sequence[Frame], options: Optional[RunOptions] = None) -> RunReport:
        self._require_connected()
        opts = options or RunOptions()
        acks = []
        faults = []
        
        for frame in frames:
            ack = self.apply_frame(frame)
            acks.append(ack)
            if not ack.ok:
                faults.extend(ack.faults)
                if not opts.allow_partial:
                    return RunReport(ok=False, last_seq=frame.seq, acks=tuple(acks), faults=tuple(faults))
        
        ok = all(a.ok for a in acks)
        last_seq = frames[-1].seq if frames else self._last_seq
        return RunReport(ok=ok, last_seq=last_seq, acks=tuple(acks), faults=tuple(faults))
    
    def read_observations(self, since_seq: Optional[int] = None) -> List[Observation]:
        self._require_connected()
        if since_seq is None:
            return list(self._observations)
        return [o for o in self._observations if o.seq > since_seq]
    
    def get_health(self) -> HealthReport:
        self._require_connected()
        flags = []
        if self._estopped:
            flags.append("ESTOPPED")
        return HealthReport(ok=not self._estopped, flags=tuple(flags))
    
    def estop(self) -> None:
        self._require_connected()
        
        # Send ESTOP to hardware
        if self._serial:
            self._serial.write(b"ESTOP\n")
            self._serial.readline()
        
        self._estopped = True
    
    def reset(self) -> None:
        self._require_connected()
        
        # Send RESET to hardware
        if self._serial:
            self._serial.write(b"RESET\n")
            self._serial.readline()
        
        self._estopped = False
        self._observations.clear()
        self._last_frame_time = None
    
    def _require_connected(self) -> None:
        if not self._connected:
            raise SubstrateError(Fault(FaultCode.UNKNOWN, "Not connected"))
```

---

## 4. Hardware Translation Formulas

From `specs/physics_engine.md`, Section 5.1:

### Phi → Voltage

The physics engine's field potential (Φ) maps to actuation voltage:

```python
import math

def phi_to_voltage(phi: float, v_max: float = 300.0) -> float:
    """
    Convert field potential to actuation voltage.
    
    Formula: V_applied = V_max * sqrt(Phi_local)
    
    Args:
        phi: Field potential (0.0 to 0.95)
        v_max: Maximum voltage
        
    Returns:
        Voltage to apply
    """
    return v_max * math.sqrt(max(0, min(phi, 0.95)))

# Examples:
# phi=0.80 → 268V (89% of max)
# phi=0.50 → 212V (71% of max)
# phi=0.95 → 292V (97% of max)
```

### Optical-path cost → Duration

The optical-path cost of an edge (Geodesic Meters; see
`specs/physics_engine.md`) can be mapped to actuation duration on a
backend-suggested basis:

```python
def path_cost_to_duration_ms(cost_gm: float, k_viscosity: float = 10.0) -> int:
    """
    Convert optical-path cost (Geodesic Meters) to actuation duration.

    Formula: Duration_ms = S_edge * k_viscosity

    Args:
        cost_gm: Discrete Fermat optical-path cost in Geodesic Meters
        k_viscosity: Hardware-specific viscosity constant (ms/Gm)

    Returns:
        Duration in milliseconds
    """
    return int(cost_gm * k_viscosity)

# Example: cost = 2.0 Gm with k = 10 → 20 ms actuation
```

---

## 5. Safety Requirements

### Watchdog (Dead Man's Switch)

Your driver **MUST** implement `max_schedule_horizon_ms`:

```python
def apply_frame(self, frame: Frame) -> Ack:
    now = time.monotonic()
    horizon_ms = self._cap.timing.max_schedule_horizon_ms
    
    if horizon_ms and self._last_frame_time is not None:
        elapsed_ms = (now - self._last_frame_time) * 1000
        if elapsed_ms > horizon_ms:
            self._estopped = True
            return Ack(
                seq=frame.seq,
                ok=False,
                faults=(Fault(FaultCode.ESTOP, "Watchdog timeout"),)
            )
    
    self._last_frame_time = now
    # ... continue with actuation
```

This ensures hardware disengages if the control system crashes.

### E-Stop

The `estop()` method must **immediately** disable all electrodes:

```python
def estop(self) -> None:
    # Send hardware-specific disable command
    self._serial.write(b"ESTOP\n")
    self._estopped = True
```

### Voltage/Frequency Bounds

Always validate against declared ranges:

```python
def set_waveform(self, wf: WaveformProfile) -> None:
    if not (self._cap.voltage_range.v_min <= wf.voltage_v <= self._cap.voltage_range.v_max):
        raise SubstrateError(Fault(
            FaultCode.UNDERVOLTAGE,
            f"Voltage {wf.voltage_v}V outside range [{self._cap.voltage_range.v_min}, {self._cap.voltage_range.v_max}]"
        ))
```

---

## 6. Future Sensing Integration Sketch - Not Current Alpha

If future hardware supports sensing, a future driver might implement `read_observations()` as shown
below. Current alpha has simulator-backed Observation v1 snapshots only; this is not sensor proof.

```python
def read_observations(self, since_seq: Optional[int] = None) -> List[Observation]:
    observations = []
    
    # Read camera-based occupancy (if available)
    if self._has_camera:
        occupancy = self._camera.detect_droplets()
        observations.append(Observation(
            seq=self._last_seq,
            time_ms=self._time_ms,
            source=ObservationSource.VISION,
            signals={"occupancy": occupancy, "confidence": 0.95},
        ))
    
    # Read impedance (if available)
    if self._has_impedance:
        impedance_map = self._read_all_impedance()
        observations.append(Observation(
            seq=self._last_seq,
            time_ms=self._time_ms,
            source=ObservationSource.IMPEDANCE,
            signals={"impedance_pf": impedance_map},
        ))
    
    # Filter by since_seq
    if since_seq is not None:
        observations = [o for o in observations if o.seq > since_seq]
    
    return observations
```

See [Sensing Integration Guide](SENSING_INTEGRATION.md) for full v3.0 details.

---

## 7. Future Driver Test Sketch - Not Current Alpha

These commands are future-driver planning notes. They are not current release validation steps and do
not imply hardware support.

### Unit Tests

Run the substrate API test suite:

```bash
python tests/test_substrate_api.py
```

### Conformance Tests

Test against the full vector suite:

```bash
# With mock backend (validates harness)
python tests/conform.py --backend mock

# With your driver (future: --backend substrate)
python tests/conform.py --backend simulator
```

### Manual Validation Sketch

```python
from your_module import OpenDropDriver

drv = OpenDropDriver()
drv.connect("serial:///dev/ttyUSB0:115200")

# Check capabilities
print(drv.get_capabilities())

# Test single frame
from klein.substrate.api import Frame
ack = drv.apply_frame(Frame(seq=1, active_electrodes=(0, 1), duration_ms=100))
print(f"Frame result: {ack.ok}")

# Clean shutdown
drv.estop()
```

---

## 8. Capabilities Schema Reference

Your driver's capabilities should align with `schemas/capabilities.schema.json`:

| Field | Description | Required |
|-------|-------------|----------|
| `backend.vendor` | Your company name | ✓ |
| `backend.firmware_id` | Firmware version | ✓ |
| `substrate.kind` | `"dmf"` or `"continuous"` | ✓ |
| `substrate.electrodes.max_count` | Total electrodes | ✓ |
| `actuation.timing.max_schedule_horizon_ms` | Watchdog timeout | ✓ |
| `actuation.waveforms.modes` | `["AC"]`, `["DC"]`, or both | ✓ |
| `sensing.channels` | Sensing capabilities | Optional |

---

## 9. Future Driver Checklist - Not Current Alpha

Before considering a future hardware driver complete:

- [ ] Implements all `SubstrateDriver` protocol methods
- [ ] Reports accurate `CapabilityProfile`
- [ ] Implements watchdog timeout (`max_schedule_horizon_ms`)
- [ ] E-stop immediately disables all electrodes
- [ ] Voltage/frequency validated against declared ranges
- [ ] Returns appropriate `FaultCode` on hardware errors
- [ ] Electrode ID bounds checked
- [ ] Frame duration validated against `min_frame_ms`
- [ ] `reset()` clears estop state
- [ ] Observations recorded for each frame
- [ ] Passes `test_substrate_api.py` tests

---

## 10. Getting Help

- **API Reference:** [docs/API.md](API.md)
- **Substrate API Source:** `src/klein/substrate/api.py`
- **Example Stub:** `OpenDropDriverStub` in `api.py`
- **Physics Translation:** `specs/physics_engine.md` Section 5
- **GitHub Issues:** Report driver integration problems

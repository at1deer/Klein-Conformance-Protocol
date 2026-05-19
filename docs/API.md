# Klein Conformance Protocol - API Reference

This document provides a complete API reference for the Klein Conformance Protocol Python library.

---

## Table of Contents

- [Core Models](#core-models)
- [Physics Engine](#physics-engine)
- [Simulator](#simulator)
- [Substrate API](#substrate-api)
- [Conformance Testing](#conformance-testing)
- [Utilities](#utilities)
- [Glossary](#glossary)

---

## Core Models

Module: `klein.common.models`

All models are Pydantic v2 with strict validation.

### Base Classes

```python
class StrictModel(BaseModel):
    """Base model with strict=True, extra='forbid'"""
    
class StrictModelAllowExtra(BaseModel):
    """Base model with strict=True, extra='allow' (forward compat)"""
```

---

### KleinProject

The main project file format (`.klein`).

```python
from klein.common.models import KleinProject

project = KleinProject.model_validate({
    "meta": {
        "version": "1.0",
        "target_substrate": "dmf.muxed_ewod.opendrop.v1.0",
        "biosafety_level": 1,
        "solver_mode": "GEODESIC"  # or "HAMILTONIAN" (future)
    },
    "nodes": [
        {"id": "A", "type": "Source", "pos": [0, 0, 0]},
        {"id": "B", "type": "Junction", "pos": [10, 0, 0]},
        {"id": "C", "type": "Sink", "pos": [20, 0, 0]},
    ],
    "edges": [
        {"from": "A", "to": "B", "type": "rail", "impedance": 0.5},
        {"from": "B", "to": "C", "type": "rail", "impedance": 1.0},
    ],
    "fields": [
        {"type": "gravity_well", "center": [15, 0, 0], "strength": 0.5, "radius": 5.0},
    ]
})
```

#### KleinMeta

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `version` | `str` | required | Protocol version |
| `target_substrate` | `str` | required | Hardware target identifier |
| `author` | `str` | `None` | Project author |
| `biosafety_level` | `1\|2\|3\|4` | `1` | BSL classification |
| `solver_mode` | `GEODESIC\|HAMILTONIAN` | `GEODESIC` | Solver algorithm |
| `resources` | `list[str]` | `None` | External resource refs |

#### KleinNode

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `id` | `str` | required | Unique node identifier |
| `type` | `str` | required | Node type (Source, Sink, Junction, etc.) |
| `pos` | `list[int]` | required | 3D position `[x, y, z]` |
| `ports` | `dict[str, PortDirection]` | `None` | Port connections |
| `state` | `int\|float` | `None` | Initial state value |

#### KleinEdge

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `from` | `str` | required | Source node ID |
| `to` | `str` | required | Target node ID |
| `type` | `str` | required | Edge type (rail, bridge, etc.) |
| `impedance` | `float` | `None` | Edge impedance (0.0-1.0) |
| `metric_tensor` | `3x3 matrix` | `None` | Reserved for v2.0 |

#### KleinField

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | `str` | required | `gravity_well` or `repulsor` |
| `center` | `list[float]` | required | 3D position |
| `strength` | `float` | required | Field strength |
| `radius` | `float` | `None` | Falloff radius |

---

### StateImageBundle (SImgB)

Static hardware configuration for compile-time routing. Formerly known as Device State Bundle (DSB).

```python
from klein.common.models import StateImageBundle

simgb = StateImageBundle.model_validate({
    "device_id": "opendrop-001",
    "geometry_hash": "abc123...",
    "defects": {
        "dead_channels": [17, 42],
        "high_impedance_regions": [100, 101]
    },
    "calibration": {
        "hash": "def456...",
        "map": {"17": 1.2, "18": 0.95}
    }
})
```

---

### Manifest

Package manifest for compiled containers.

```python
from klein.common.models import Manifest

manifest = Manifest.model_validate({
    "project": {
        "name": "my-experiment",
        "version": "1.0.0",
        "authors": ["Alice", "Bob"],
        "license": "MIT"
    },
    "runtime": {
        "mode": "HARD",  # HARD | ENVELOPE | DIAGNOSTIC
        "target_substrate": "dmf.muxed_ewod.opendrop.v1.0",
        "biosafety_level": 1
    }
})
```

---

### Container

Compiled container format (`.kleinc`).

```python
from klein.common.models import Container, ContainerPayload

container = Container.model_validate({
    "klein_container_version": "1.0",
    "manifest": manifest_data,
    "payload": {
        "kind": "CHANNEL_LIST",
        "data": [[1, 2, 3], [4, 5, 6]],
        "encoding": "JSON"
    },
    "simgb": simgb_data,  # optional
    "runbook": runbook_data  # optional
})
```

#### PayloadKind

- `CHANNEL_LIST`: List of active channels per frame
- `FRAME_SEQUENCE`: Full frame objects
- `BITMAP_SEQUENCE`: Binary electrode bitmaps

#### PayloadEncoding

- `JSON`: Plain JSON array
- `BASE64_GZIP`: Base64-encoded gzipped data
- `RLE`: Run-length encoded

---

### HAIL Events (Hardware Audit & Integrity Log)

HAIL log event types. Formerly known as SCI (Standard Compliance Interface).

```python
from klein.common.models import (
    DeviceEvent,
    MeasurementEvent,
    ECRPAttemptEvent,  # Formerly LCPAttemptEvent
    ReplanDecisionEvent,
    RuntimeStateSnapshotEvent,
)

# All events share these base fields:
# - t: int (tick/timestamp)
# - timebase: "DEVICE_TICKS" | "WALL_MS"
# - run_id: str
# - kind: str (discriminator)
```

#### Event Types

| Kind | Purpose | Key Fields |
|------|---------|------------|
| `DEVICE_EVENT` | Hardware events | `code`, `level`, `message`, optional `detail` |
| `MEASUREMENT` | Sensor readings | `detector_id`, `value` |
| `ECRP_ATTEMPT` | Recovery attempt evidence (ECRP) | `strategy`, `attempt_index`, `outcome`, `deltas` |
| `REPLAN_DECISION` | Path recalculation | `checkpoint_id`, `seed`, `inputs_ref` |
| `RUNTIME_STATE_SNAPSHOT` | State capture | `rimgb_hash`, `validity_window` |

---

### Trace

Execution trace for debugging and reproducibility.

```python
from klein.common.models import Trace, TracePlan, TraceOp, ActuationRef, TickRange

trace = Trace.model_validate({
    "trace_version": "1.0",
    "tick_range": {"start": 0, "end": 100},
    "plans": [
        {
            "plan_id": "plan_1",
            "ops": [
                {
                    "op_id": "move_A_to_B",
                    "actuation_refs": [
                        {
                            "channel_id": 17,
                            "tick_range": {"start": 0, "end": 10},
                            "kind": "ACTUATION"
                        }
                    ]
                }
            ]
        }
    ]
})
```

---

## Physics Engine

Module: `klein.sim.physics`

### Constants

```python
EPSILON = 0.001       # Base action constant
PHI_CLAMP_MAX = 0.95  # Maximum field potential
```

### FieldManager

Manages volumetric field calculations.

```python
from klein.sim.physics import FieldManager
from klein.common.models import KleinField

fields = [
    KleinField(type="gravity_well", center=[10, 0, 0], strength=0.5, radius=5.0),
    KleinField(type="repulsor", center=[5, 5, 0], strength=0.3, radius=3.0),
]

fm = FieldManager(fields)

# Get potential at a point
phi = fm.get_potential([10, 0, 0])  # Returns 0.0 to 0.95

# Get potential map for entire graph
potential_map = fm.get_potential_map(graph, positions)
```

### GeodesicSolver

A* pathfinder with impedance and field costs.

```python
from klein.sim.physics import GeodesicSolver, build_graph

# Build graph from project
graph, positions = build_graph(project)

# Create solver
solver = GeodesicSolver(graph, positions, field_manager)

# Solve for path
result = solver.solve(source="A", sink="C")

# Result fields:
#   result.success: bool
#   result.path: list[str]
#   result.total_cost: float
#   result.explored_count: int
#   result.edge_count: int
```

### WaveSolver

Stochastic reachability analysis.

```python
from klein.sim.physics import WaveSolver

wave_solver = WaveSolver(graph, positions, field_manager)
probs = wave_solver.compute_reachability(source="A", steps=10)

# probs: dict[node_id, probability]
```

### Action Cost Formula

```
S(edge) = L * (Z + epsilon) * (1 - Phi)

Where:
  L = Euclidean distance between nodes
  Z = Edge impedance (0.0 = superconductor, 1.0 = standard)
  epsilon = 0.001 (prevents division by zero)
  Phi = Field potential at edge midpoint (clamped to 0.95)
```

---

## Simulator

Module: `klein.sim`

The Klein simulator package provides two levels of simulation:

1. **SimulationRunner** (`klein.sim.runner`) - A* pathfinding on `.klein` project graphs
2. **ExecutionEngine** (`klein.sim.execution_engine`) - Full container execution with droplet physics

---

### SimulationRunner (Pathfinding Only)

Runs A* geodesic pathfinding on a `.klein` project.

```python
from klein.sim.runner import SimulationRunner, load_project

project = load_project("project.klein")

runner = SimulationRunner(
    project=project,
    simgb=None,        # Optional StateImageBundle
    seed=42,           # Random seed for determinism
    output=sys.stdout, # Output stream for JSONL
)

runner.emit_startup()
success = runner.run_geodesic(source="A", sink="C")
runner.finalize()
```

---

### VirtualSubstrate (Droplet Physics)

Full substrate simulation with droplet tracking and impedance sensing.

```python
from klein.sim import VirtualSubstrate

# Create virtual substrate (16x8 electrode grid)
substrate = VirtualSubstrate(
    max_channels=128,
    grid_width=16,
    grid_height=8,
    seed=42,
    stuck_probability=0.01,  # 1% chance droplet sticks
)
substrate.connect("virtual://test")

# Spawn a droplet at electrode 10
substrate.spawn_droplet("drop1", electrode_id=10)

# Apply frame - droplet moves to activated adjacent electrode
from klein.substrate.api import Frame
frame = Frame(seq=1, active_electrodes=(11,), duration_ms=20)
ack = substrate.apply_frame(frame)

# Check droplet position
positions = substrate.get_droplet_positions()
print(positions)  # {'drop1': 11}

# Read simulated impedance
impedance = substrate.read_impedance_map()
print(impedance[11])  # ~50kΩ (droplet present)
print(impedance[10])  # ~10MΩ (empty)
```

#### Validation

```python
# Configure expected hashes for SImgB validation
substrate.configure_validation(
    geometry_hash="expected_geo_hash",
    calibration_hash="expected_cal_hash",
    dead_channels=[17, 42],
)

# Validate a SImgB - returns list of ValidationError
errors = substrate.validate_simgb({
    "geometry_hash": "wrong_hash",
    "calibration": {"hash": "also_wrong"},
})

for err in errors:
    print(err.code, err.message)  # SIMGB_GEOMETRY_MISMATCH, ...
```

---

### ExecutionEngine (Container Execution)

Executes `.kleinc` containers with full HAIL event emission.

```python
from klein.sim import (
    VirtualSubstrate,
    ExecutionEngine,
    ExecutionConfig,
    HAILEmitter,
)
from klein.common.models import Container
import io

# Load container
container = Container.model_validate(json.load(open("exp.kleinc")))

# Setup
output = io.StringIO()
substrate = VirtualSubstrate()
substrate.connect("virtual://test")

emitter = HAILEmitter(output=output, run_id="run_001")
config = ExecutionConfig(
    ecrp_enabled=True,
    ecrp_max_attempts=3,
    emit_frame_events=True,
    emit_observations=True,
)

engine = ExecutionEngine(
    substrate=substrate,
    emitter=emitter,
    config=config,
)

# Execute container
result = engine.execute_container(container)

print(f"Success: {result.success}")
print(f"Frames executed: {result.frames_executed}")
print(f"Errors: {result.errors}")

# Read HAIL events
output.seek(0)
for line in output:
    event = json.loads(line)
    print(event["kind"], event.get("code", ""))
```

---

### PayloadParser

Converts container payloads to frame sequences.

```python
from klein.sim import PayloadParser, PayloadKind

parser = PayloadParser(default_duration_ms=20)

# Parse CHANNEL_LIST payload
payload = {
    "kind": "CHANNEL_LIST",
    "encoding": "JSON",
    "data": [
        {"t": 0, "channel_id": 10, "state": "ON", "voltage_v": 200.0},
        {"t": 0, "channel_id": 11, "state": "ON", "voltage_v": 200.0},
        {"t": 10, "channel_id": 12, "state": "ON", "voltage_v": 200.0},
    ],
}

sequence = parser.parse_container_payload(payload)
print(f"Parsed {len(sequence.frames)} frames")
# Frames grouped by tick: t=0 → electrodes 10,11; t=10 → electrode 12
```

Supported payload kinds:
- `CHANNEL_LIST`: `{t, channel_id, state, voltage_v, frequency_hz?}`
- `FRAME_SEQUENCE`: `{t, format, data}` (sparse, bitmap, delta_tiles)
- `BITMAP_SEQUENCE`: Base64-encoded bitmaps

---

### CLI Usage

```bash
# Basic A* pathfinding
python -m klein.sim.runner project.klein --source A --sink C

# With ECRP enabled
python -m klein.sim.runner project.klein -s A -t C --ecrp --max-attempts 3

# With trace output
python -m klein.sim.runner project.klein -s A -t C --trace trace.json

# Output to file
python -m klein.sim.runner project.klein -s A -t C -o events.jsonl
```

---

## Substrate API

Module: `klein.substrate.api`

### SubstrateDriver Protocol

The hardware abstraction interface.

```python
from klein.substrate.api import SubstrateDriver

class SubstrateDriver(Protocol):
    def connect(self, uri: str) -> None: ...
    def get_capabilities(self) -> CapabilityProfile: ...
    def get_topology(self) -> ElectrodeTopology: ...
    def set_waveform(self, wf: WaveformProfile) -> None: ...
    def apply_frame(self, frame: Frame) -> Ack: ...
    def run_sequence(self, frames: Sequence[Frame], options: RunOptions = None) -> RunReport: ...
    def read_observations(self, since_seq: int = None) -> list[Observation]: ...
    def get_health(self) -> HealthReport: ...
    def estop(self) -> None: ...
    def reset(self) -> None: ...
```

### MockSubstrate

Reference implementation for testing.

```python
from klein.substrate.api import (
    MockSubstrate, Frame, WaveformProfile, WaveformMode,
    FaultRule, Fault, FaultCode, TimingProfile
)

# Create mock with custom timing (watchdog enabled)
timing = TimingProfile(
    min_frame_ms=5,
    max_schedule_horizon_ms=1000  # 1 second watchdog
)

drv = MockSubstrate(max_channels=128, timing=timing)
drv.connect("mock://test")

# Configure waveform
drv.set_waveform(WaveformProfile(
    mode=WaveformMode.AC,
    voltage_v=200.0,
    ac_frequency_hz=1000.0
))

# Execute frames
frames = [
    Frame(seq=1, active_electrodes=(17, 18), duration_ms=20),
    Frame(seq=2, active_electrodes=(18, 19), duration_ms=20),
]

report = drv.run_sequence(frames)
print(f"Success: {report.ok}, Last seq: {report.last_seq}")
```

### Fault Injection (CI Testing)

```python
# Add deterministic fault for testing
drv.add_fault_rule(FaultRule(
    when_seq=3,  # Trigger on frame 3
    fault=Fault(FaultCode.OVERCURRENT, "Test fault", {"channel": 17}),
    once=True,   # Only fire once
))

# Or trigger on specific electrode
drv.add_fault_rule(FaultRule(
    when_contains_electrode=42,
    fault=Fault(FaultCode.CHANNEL_UNAVAILABLE, "Electrode 42 blocked"),
))
```

### FaultCode Reference

| Code | Description |
|------|-------------|
| `E_OVERRIDE` | Generic driver override |
| `E_OVERCURRENT` | Current limit exceeded |
| `E_UNDERVOLTAGE` | Voltage below minimum |
| `E_FRAME_TOO_FAST` | Frame duration below minimum |
| `E_CHANNEL_UNAVAILABLE` | Electrode unavailable |
| `E_CARTRIDGE_MISMATCH` | Wrong cartridge installed |
| `E_SENSE_UNAVAILABLE` | Sensor not available |
| `E_EXECUTION_ABORTED` | E-stop or abort triggered |
| `E_ESTOP` | Watchdog timeout |
| `E_UNKNOWN` | Unknown error |

---

## Conformance Testing

Module: `tests/conform.py`

### Running Tests

```bash
# All vectors
python tests/conform.py

# Specific vectors
python tests/conform.py --vector 001 --vector 113

# Filter by category
python tests/conform.py --category positive
python tests/conform.py --category negative

# Use in-process simulator (faster)
python tests/conform.py --backend simulator

# JSON output for CI
python tests/conform.py --json > results.json
```

### Comparison Modes

| Mode | Description |
|------|-------------|
| `EXACT_JSONL` | Byte-for-byte canonical match |
| `SET` | Order-independent set comparison |
| `ENVELOPE` | Numeric tolerances allowed |

### Backend Types

| Backend | Description |
|---------|-------------|
| `mock` | Returns golden observables (harness testing) |
| `subprocess` | Calls klein-sim via subprocess |
| `simulator` | In-process Python API |
| `substrate` | Direct hardware (future) |

---

## Utilities

### Canonicalization

```python
from klein.hail.canonical import dump_canonical

event = {"kind": "DEVICE_EVENT", "t": 0, "run_id": "abc", "code": "INIT", "level": "INFO", "message": "Run initialized"}
canonical_json = dump_canonical(event)
# Output: {"code":"INIT","kind":"DEVICE_EVENT","level":"INFO","message":"Run initialized","run_id":"abc","t":0}
```

`dump_canonical` uses Klein HAIL event ordering plus RFC 8785 / JCS canonical JSON for each
event. Use the `klein-hail-canon` CLI for file-level verification and digest checks.

### Hash Computation

```python
from pathlib import Path

from klein.common.hashing import canonical_json_sha256_ref, hash_json_artifact
from klein.sim.runner import compute_rimgb_hash

# Hash JSON-compatible data using Klein canonical JSON v1.
h = canonical_json_sha256_ref({"key": "value"})

# Hash a .klein or .kleinc artifact from canonical bytes.
artifact = hash_json_artifact(Path("input/project.klein"))

# Compute an evidence-bound RImgB hash reference.
rimgb = compute_rimgb_hash(project, simgb, timestamp_ms)
```

Externally reported evidence-bound hashes use `sha256:<hex>` form. Malformed artifacts may still
be reported with a raw byte hash, but Klein does not assign a canonical artifact hash unless the
artifact parses as the declared canonical input type.

---

## Error Handling

### SubstrateError

```python
from klein.substrate.api import SubstrateError, Fault, FaultCode

try:
    drv.apply_frame(frame)
except SubstrateError as e:
    print(f"Fault: {e.fault.code}")
    print(f"Message: {e.fault.message}")
    print(f"Detail: {e.fault.detail}")
```

### Validation Errors

All models use Pydantic validation:

```python
from pydantic import ValidationError
from klein.common.models import KleinProject

try:
    project = KleinProject.model_validate(invalid_data)
except ValidationError as e:
    for error in e.errors():
        print(f"{error['loc']}: {error['msg']}")
```

---

## Type Aliases

```python
from klein.common.models import (
    SImgB,  # = StateImageBundle
    DSB,    # = StateImageBundle (deprecated alias)
    Kln,    # = KleinProject (deprecated)
    Klnc,   # = Container (deprecated)
)
```

---

## Glossary

See the complete [Glossary of Terms](GLOSSARY.md) for all terminology definitions.

| New Term | Full Name | Formerly |
|----------|-----------|----------|
| HAIL | Hardware Audit & Integrity Log | SCI |
| SImgB | State Image Bundle | DSB |
| RImgB | Runtime Image Bundle | RSB |
| ECRP | Error Correction & Recovery Protocol | LCP |
| `.klein` | Klein Project File | `.kln` |
| `.kleinc` | Klein Compiled Container | `.klnc` |

---

## Version Information

```python
SOLVER_VERSION = "klein-sim/1.0.0"
```

---

## See Also

- [Glossary of Terms](GLOSSARY.md)
- [Protocol Specification](../specs/klein_protocol_master.md)
- [Physics Engine](../specs/physics_engine.md)
- [Canonicalization Rules](../specs/algorithms/klein_canon.jsonl.v1.md)

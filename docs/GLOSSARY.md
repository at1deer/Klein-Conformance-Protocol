# Klein Conformance Protocol - Glossary of Terms

This glossary defines the official terminology used throughout the Klein Conformance Protocol.

---

## Core Protocol Terms

### Klein Conformance Protocol

The core protocol specification for bounded physical execution under uncertainty. It defines artifact formats, canonical runtime evidence, recovery-attempt logging, and conformance testing.

---

## File Formats

### `.klein`

**Klein Project File**

The primary project file format containing graph definitions, metadata, and field configurations for geodesic path computation.

```json
{
  "meta": { "version": "1.0", "target_substrate": "..." },
  "nodes": [...],
  "edges": [...],
  "fields": [...]
}
```

Previously: `.kln`

---

### `.kleinc`

**Klein Compiled Container**

A self-contained package bundling manifest, payload data, and optional SImgB/runbook for execution.

```json
{
  "klein_container_version": "1.0",
  "manifest": {...},
  "payload": {...},
  "simgb": {...},
  "runbook": {...}
}
```

Previously: `.klnc`

---

## State Bundles

### SImgB (State Image Bundle)

**Static hardware configuration captured at compile time.**

Contains:
- Device identification
- Geometry hash
- Known defects (dead channels, high impedance regions)
- Calibration data

Used for: Compile-time routing decisions, runtime verification.

Previously: DSB (Device State Bundle)

---

### RImgB (Runtime Image Bundle)

**Dynamic state captured at runtime.**

Contains:
- Current environment conditions
- Sensor readings
- Time-varying calibration drift

Captured via: `RUNTIME_STATE_SNAPSHOT` events in the HAIL log.

Previously: RSB (Runtime State Bundle)

---

## Logging & Audit

### HAIL (Hardware Audit & Integrity Log)

**The standardized event log format for runtime execution.**

A JSONL stream of typed events that provides:
- Canonical runtime evidence
- Runtime state snapshots
- Recovery-attempt evidence
- Measurement records

Event kinds:
- `DEVICE_EVENT` - Hardware state changes
- `MEASUREMENT` - Sensor readings
- `ECRP_ATTEMPT` - Error correction attempts
- `REPLAN_DECISION` - Path recalculation events
- `RUNTIME_STATE_SNAPSHOT` - State capture

Output artifact: `*.hail.jsonl` or embedded in execution output.

Previously: SCI (Standard Compliance Interface)

---

## Error Handling

### ECRP (Error Correction & Recovery Protocol)

**The protocol surface for bounded recovery attempts and evidence.**

Features:
- Bounded retry attempts (`max_attempts`)
- Evidence logging for every correction
- Explicit success, partial, no-change, or failure outcomes

Event: `ECRP_ATTEMPT` records each correction attempt with:
- `attempt_index` - Sequential attempt number
- `outcome` - SUCCESS, FAIL, PARTIAL, or NO_CHANGE
- `deltas` - Changes made
- `parameters` - Correction parameters used

Previously: LCP (Local Correction Protocol)

---

## Execution Modes

### HARD Mode

Exact byte-for-byte comparison. Any divergence from expected output is a failure.

Use case: Production validation, CI/CD gates.

---

### ENVELOPE Mode

Comparison with declared tolerances. Numeric values within tolerance bounds pass.

Use case: Hardware-in-loop testing, physical substrate validation.

---

### DIAGNOSTIC Mode

Nonconformant exploratory mode. Always labeled NONCONFORMANT but execution proceeds.

Use case: Debugging, calibration, new substrate development.

---

## Physics & Routing

### Geodesic Routing

Treating execution as finding the **Path of Least Action** through a physical cost surface.

Formula:
```
S(P) = Σ [ L × (Z + ε) × (1 - Φ) ]
```

Where:
- `L` = Edge length (Euclidean distance)
- `Z` = Impedance (0.0 = superconductor, 1.0 = standard)
- `ε` = Base action constant (0.001)
- `Φ` = Field potential (gravity wells, repulsors)

---

### Gravity Well

A volumetric field that attracts paths toward its center by reducing action cost.

```json
{
  "type": "gravity_well",
  "center": [x, y, z],
  "strength": 0.0-1.0,
  "radius": falloff_distance
}
```

---

### Repulsor

A volumetric field that repels paths away from its center by increasing action cost.

```json
{
  "type": "repulsor",
  "center": [x, y, z],
  "strength": 0.0-1.0,
  "radius": falloff_distance
}
```

---

## Hardware Terms

### Substrate

The physical programmable matter platform. Examples:
- EWOD (Electrowetting on Dielectric)
- DMF (Digital Microfluidics)
- Soft robotics actuators
- Biological computing substrates

---

### Watchdog Timer

A safety mechanism that triggers an emergency stop (E_ESTOP) if frames are not received within `max_schedule_horizon_ms`.

Ensures hardware disengages if the control system fails.

---

### Frame

A single actuation command to the substrate.

```python
Frame(
    seq=1,                        # Sequence number
    active_electrodes=(17, 18),   # Channels to activate
    duration_ms=20,               # Duration
    wf_override=None              # Optional waveform override
)
```

---

## Conformance Testing

### Test Vector

A packaged test case containing:
- Manifest (execution configuration)
- Payload (actuation data)
- Expected results (golden observables)

Stored as `.kleinc` containers or loose folder format.

---

### Compare Modes

| Mode | Description |
|------|-------------|
| `EXACT_JSONL` | Byte-for-byte canonical match |
| `SET` | Order-independent set comparison |
| `ENVELOPE` | Numeric tolerances allowed |

---

## Abbreviation Reference

| New Term | Full Name | Formerly |
|----------|-----------|----------|
| HAIL | Hardware Audit & Integrity Log | SCI |
| SImgB | State Image Bundle | DSB |
| RImgB | Runtime Image Bundle | RSB |
| ECRP | Error Correction & Recovery Protocol | LCP |
| `.klein` | Klein Project File | `.kln` |
| `.kleinc` | Klein Compiled Container | `.klnc` |

---

## See Also

- [API Reference](API.md)
- [Protocol Specification](../specs/klein_protocol_master.md)
- [Physics Engine](../specs/physics_engine.md)

# Examples

This directory contains public examples and release/demo material.

- `examples/public-alpha/`: public-alpha demo package for verifying a KCP bundle, validating a
  recorded-run archive, exercising the OpenDrop/EWOD dry-run adapter skeleton, and running the Rust
  cross-language verifier.

The public-alpha examples focus on evidence, conformance, and verification. They do not claim
hardware support, HIL execution, physical truth, sensor proof, timestamp proof, hardware attestation proof, TPM/TEE verification,
real OpenDrop control, or production certification.
# Klein Example Projects

This folder contains example `.klein` project files demonstrating various Klein Conformance Protocol features.

## Examples

### 1. Simple Path (`simple_path.klein`)

A minimal linear graph with 5 nodes and uniform impedance.

```bash
python -m klein.sim.runner examples/simple_path.klein --source source --sink sink
```

**Features demonstrated:**
- Basic node/edge structure
- Impedance values
- Source → Sink pathfinding

### 2. Gravity Well (`gravity_well.klein`)

A graph with multiple paths where a gravity well attracts the solver toward one route.

```bash
python -m klein.sim.runner examples/gravity_well.klein --source source --sink sink
```

**Features demonstrated:**
- Multiple path options
- Gravity well field effect
- Cost optimization with field potential

### 3. Obstacle Avoidance (`obstacle_avoidance.klein`)

A 3x3 grid with a repulsor field at the center, forcing the solver to route around the obstacle.

```bash
python -m klein.sim.runner examples/obstacle_avoidance.klein --source source --sink sink
```

**Features demonstrated:**
- Grid topology
- Repulsor field effect
- Path deviation around obstacles

---

## Running Examples

### Basic Execution

```bash
# Run with default settings
python -m klein.sim.runner examples/simple_path.klein -s source -t sink

# With trace output
python -m klein.sim.runner examples/simple_path.klein -s source -t sink --trace trace.json

# Save HAIL events to file
python -m klein.sim.runner examples/simple_path.klein -s source -t sink -o events.jsonl
```

### With SImgB (State Image Bundle)

```bash
python -m klein.sim.runner examples/simple_path.klein -s source -t sink --simgb device.json
```

### Deterministic Execution

```bash
# Use fixed seed for reproducibility
python -m klein.sim.runner examples/simple_path.klein -s source -t sink --seed 42
```

---

## Creating Your Own Project

```json
{
  "meta": {
    "version": "1.0",
    "target_substrate": "dmf.muxed_ewod.opendrop.v1.0",
    "author": "Your Name",
    "biosafety_level": 1,
    "solver_mode": "GEODESIC"
  },
  "nodes": [
    { "id": "A", "type": "Source", "pos": [0, 0, 0] },
    { "id": "B", "type": "Junction", "pos": [10, 0, 0] },
    { "id": "C", "type": "Sink", "pos": [20, 0, 0] }
  ],
  "edges": [
    { "from": "A", "to": "B", "type": "rail", "impedance": 1.0 },
    { "from": "B", "to": "C", "type": "rail", "impedance": 1.0 }
  ],
  "fields": [
    {
      "type": "gravity_well",
      "center": [15, 0, 0],
      "strength": 0.5,
      "radius": 10.0
    }
  ]
}
```

---

## Field Types

### Gravity Well

Attracts the solver path toward its center. Reduces action cost for nearby edges.

```json
{
  "type": "gravity_well",
  "center": [x, y, z],
  "strength": 0.0 - 1.0,
  "radius": falloff_distance
}
```

### Repulsor

Repels the solver path away from its center. Increases action cost for nearby edges.

```json
{
  "type": "repulsor",
  "center": [x, y, z],
  "strength": 0.0 - 1.0,
  "radius": falloff_distance
}
```

---

## Terminology

| Term | Description |
|------|-------------|
| `.klein` | Klein project file format |
| SImgB | State Image Bundle (compile-time hardware config) |
| RImgB | Runtime Image Bundle (runtime state) |
| HAIL | Hardware Audit & Integrity Log (event stream) |
| ECRP | Error Correction & Recovery Protocol |

---

## See Also

- [API Documentation](../docs/API.md)
- [Glossary](../docs/GLOSSARY.md)
- [Physics Engine Specification](../specs/physics_engine.md)
- [Protocol Specification](../specs/klein_protocol_master.md)

# Klein Conformance Protocol Specification

**Version v1.0 - 2026-01-07**

> Legacy January prototype note: this document is retained for context. The current
> alpha normative core is split under `specs/core/`, `specs/artifacts/`, and
> `specs/profiles/`. Recovery, proof, and universal substrate claims are preserved
> as TARGET_V1 or LONG_HORIZON work in `docs/CLAIMS_LEDGER.md`; the split specs
> define what is currently implemented.

This document is retained as contextual January prototype material. The split v1 specs are the
current alpha normative reference for execution modes, artifacts, HAIL, profiles, and
conformance.

---

## Terminology

| Term | Full Name | Description |
|------|-----------|-------------|
| **HAIL** | Hardware Audit & Integrity Log | Cryptographic event log for execution |
| **SImgB** | State Image Bundle | Static hardware config at compile time |
| **RImgB** | Runtime Image Bundle | Dynamic state at runtime |
| **ECRP** | Error Correction & Recovery Protocol | Bounded recovery evidence |
| `.klein` | Klein Project File | Graph definition format |
| `.kleinc` | Klein Compiled Container | Bundled execution package |

---

## 0. Legal Disclaimer & Limitation of Liability
### 0.1 Not a Safety Interlock 
The Klein Conformance Protocol (KCP) and the Hardware Audit & Integrity Log (HAIL) are logic verification tools, not safety systems.

• **Compliance != Safety**: A "Conformant" backend demonstrates that it can parse instructions and log errors under the tested contract. It does not guarantee that the hardware is physically safe, electrically isolated, or biologically contained.

• **Software-Defined Safety**: Features such as the "Dead Man's Switch" and safety_estop are defined in software. They MUST NOT replace hardware-level emergency stops, fuses, or interlocks when operating with high voltage or hazardous materials.
### 0.2 High Voltage Warning 
Klein implementations often target Digital Microfluidic (DMF) substrates and other hardware operating at voltages exceeding 100V. The Protocol Authors assume NO LIABILITY for hardware damage, dielectric breakdown, or personal injury resulting from the use of this protocol. The user is solely responsible for ensuring that compiled .kleinc payloads do not exceed the physical ratings of their specific backend.
### 0.3 Biosafety Disclaimer 
While Klein supports metadata for biosafety_level (BSL), the Protocol CANNOT enforce physical containment.

• The runtime cannot prevent a BSL-1 hardware device from loading a BSL-4 protocol file.

• The user assumes full responsibility for adhering to local Biosafety Level regulations (e.g., CDC/NIH guidelines) and ensuring their hardware phenotype matches the biological risk of the reagents used.

## 1. Execution Modes

The runner MUST declare the execution mode in manifest/runtime and include it in the conformance report.

| Mode | Description | Divergence Handling |
|------|-------------|---------------------|
| HARD | Exact compare according to HAIL compare_mode | Any divergence is FAIL; must be attributable to a stage + error code |
| ENVELOPE | Compare uses declared tolerances | Backend must declare supported envelope dimensions and bounds |
| DIAGNOSTIC | Nonconformant exploratory mode | MUST label run NONCONFORMANT; MUST record all adaptations and attempts |

---

## 2. Device State: SImgB + RImgB

SImgB is the compile-time bundle. RImgB is for runtime-varying state.

### 2.1 State Image Bundle (SImgB)

Stable, compile-time state:
- Geometry and electrode topology
- Defect maps
- Calibration coefficients
- Hashed and referenced at compile time

### 2.2 Runtime Image Bundle (RImgB)

Time-varying environment and measurements:
- Emitted during run via RUNTIME_STATE_SNAPSHOT events
- Referenced by replanning decisions
- Contains validity_window for temporal bounds

Backends MUST specify which fields are stable (SImgB) versus dynamic (RImgB) in capabilities.

---

## 3. Checkpointed Replanning Contract

Replan is allowed only at CHECKPOINT boundaries unless in DIAGNOSTIC mode.

Requirements:
- REPLAN_DECISION must be emitted with deterministic seed + solver version
- Replanning inputs must be stable and referenced (SImgB hash + RImgB hash + last observables)

Error Codes:
- REPLAN_NOT_AT_CHECKPOINT: Replan attempted outside checkpoint boundary

---

## 4. Error Correction & Recovery Protocol (ECRP)

ECRP attempts MUST be deterministic and bounded by max_attempts in HARD/ENVELOPE.

Requirements:
- Each attempt MUST emit ECRP_ATTEMPT with attempt_index and outcome
- If recovery fails:
  - HARD/ENVELOPE: STOP + NONCONFORMANT
  - DIAGNOSTIC: may continue but must label run NONCONFORMANT

Error Codes:
- ECRP_MISSING_EVIDENCE: ECRP attempt without required evidence emission

---

## 5. Hardware Audit & Integrity Log (HAIL)

The HAIL defines the event log format for conformance testing and runtime observability.

### 5.1 HAIL Event Kinds

| Kind | Description | Required Fields |
|------|-------------|-----------------|
| DEVICE_EVENT | Hardware lifecycle events | code, run_id |
| MEASUREMENT | Sensor readings | measurement_id, value, unit |
| RUNTIME_STATE_SNAPSHOT | RImgB hash + state fields | rimgb_hash, validity_window |
| ECRP_ATTEMPT | Correction attempt evidence | attempt_index, parameters, outcome |
| REPLAN_DECISION | Checkpointed replanning | checkpoint_id, reason, solver_version, seed |

### 5.2 Compare Modes and Ordering

| Mode | Description |
|------|-------------|
| EXACT_JSONL | Byte-for-byte identical JSONL, including record ordering for same-t mixed kinds |
| SET | Treats each JSONL line as an element; canonicalization rules MUST be documented |
| ENVELOPE | Requires declared tolerance dimensions and bounds |

### 5.3 Canonicalization (klein.canon.jsonl.v1)

For EXACT_JSONL comparison, events are sorted by:
1. t (tick/timestamp)
2. kind (event type)
3. tie-breaker (kind-specific: measurement_id, checkpoint_id, attempt_index, etc.)

JSON serialization uses RFC 8785 / JCS per-event serialization as defined in
`specs/algorithms/klein_canon.jsonl.v1.md`.

---

## 6. Expected File Format

Test vectors include expected/expected.json with conformance criteria.

### 6.1 Capability Gating

- required_capabilities: List of strings (e.g., envelope, checkpoint_replan)
- If backend lacks required capabilities: SKIP with reason CAPABILITY_MISSING

### 6.2 Observable Requirements

- required_observables_kinds: List of event kinds that MUST be produced
- HARD/ENVELOPE: FAIL if not present
- DIAGNOSTIC: emit NONCONFORMANT evidence

---

## 7. Error Codes

| Code | Trigger |
|------|---------|
| CAPABILITY_MISSING | Backend lacks required capability (SKIP) |
| REPLAN_NOT_AT_CHECKPOINT | Replan outside checkpoint boundary |
| ECRP_MISSING_EVIDENCE | ECRP attempt without evidence emission |
| RIMGB_SCHEMA_INVALID | RImgB fails schema validation |
| EXACT_JSONL_MISMATCH | Byte-level difference in EXACT_JSONL mode |
| ENVELOPE_EXCEEDED | Value outside declared tolerance |

---

## 8. Capabilities and Negotiation

Backends MUST publish a capabilities.json; klein-conform uses it for gating suites and compare modes.

### 8.1 Required Capability Declarations

Example capabilities.json:

    {
      "supports": {
        "envelope": true,
        "diagnostic": true,
        "checkpoint_replan": true
      },
      "hail": {
        "compare": {
          "EXACT_JSONL": true,
          "SET": true,
          "ENVELOPE": true
        }
      },
      "payload": {
        "kinds": ["CHANNEL_LIST", "FRAME_SEQUENCE"],
        "encodings": ["JSON", "BASE64_GZIP"]
      }
    }

---

## 9. Profile Taxonomy and Scope Control

### 9.1 Tokenized-Carrier Profiles

Discrete carriers on a graph/grid:
- Typical for DMF and packetized pneumatics
- Carriers have discrete positions
- Success = carrier reaches sink

### 9.2 Field/Control Profiles

Continuous state estimators controlled by discrete actuators:
- Typical for continuous flow and soft robotics
- State is a continuous distribution
- Success = state enters goal region

Profiles MUST declare:
- Conserved quantities
- Success criteria
- Required observables

---

## 10. Hardware Contract

### 10.1 Substrate Driver Protocol

All hardware interaction flows through the SubstrateDriver protocol:

- connect(uri) - Establish connection
- get_capabilities() - Query device capabilities
- get_topology() - Get electrode layout
- set_waveform(wf) - Configure actuation waveform
- apply_frame(frame) - Execute single frame
- run_sequence(frames) - Execute frame sequence
- read_observations(since_seq) - Get sensor data
- get_health() - Check device status
- estop() - Emergency stop
- reset() - Reset device state

### Normative Note on Primitive Guarantees: 
Unless a capability is explicitly marked as "guarantee": "guaranteed" in the backend's capabilities.json, all primitive operations (Split, Merge, Move) are considered Best Effort. A "Success" outcome in the HAIL log indicates that the driver attempted the actuation sequence without detecting a fault, not that the physical physics occurred successfully. ECRP records bounded correction attempts; full closed-loop recovery is outside the current alpha reference simulator.

### 10.2 Watchdog Timer (Dead Man's Switch)

Safety mechanism to prevent indefinite actuation:

- TimingProfile.max_schedule_horizon_ms: Maximum time between frames
- If exceeded: Driver triggers E_ESTOP fault and disengages
- Reset via connect() or reset()

### 10.3 Fault Injection (CI Testing)

For deterministic CI tests, MockSubstrate supports programmable faults via FaultRule:

- when_seq: Trigger on specific frame sequence number
- when_contains_electrode: Trigger when frame activates specific electrode
- fault: The Fault object to inject
- once: Fire only once (default true)

Example usage:

    drv = MockSubstrate()
    drv.connect("mock://ci")
    drv.add_fault_rule(FaultRule(
        when_seq=3,
        fault=Fault(FaultCode.OVERCURRENT, "Injected OC for test")
    ))
    report = drv.run_sequence(frames)
    assert report.ok is False

### 10.4 Fault Codes

| Code | Description |
|------|-------------|
| E_OVERRIDE | Generic driver override |
| E_OVERCURRENT | Current limit exceeded |
| E_UNDERVOLTAGE | Voltage below minimum |
| E_FRAME_TOO_FAST | Frame duration below device minimum |
| E_CHANNEL_UNAVAILABLE | Electrode out of range |
| E_CARTRIDGE_MISMATCH | Wrong cartridge installed |
| E_SENSE_UNAVAILABLE | Requested sensing not available |
| E_EXECUTION_ABORTED | E-stop active |
| E_ESTOP | Watchdog timeout (Dead Man Switch) |
| E_UNKNOWN | Unclassified error |

---

## 11. Stability and Compatibility

This section defines the stability guarantees and compatibility contract for the Klein Protocol.

### 11.1 Semantic Versioning

Klein follows [Semantic Versioning 2.0.0](https://semver.org/):

| Version Component | Meaning |
|-------------------|---------|
| **MAJOR** (X.0.0) | Breaking changes to wire format, schemas, or semantics |
| **MINOR** (1.X.0) | Backwards-compatible feature additions |
| **PATCH** (1.0.X) | Backwards-compatible bug fixes |

**Alpha Stage (KCP Core v1 alpha)**: APIs, schemas, and wire formats may change without notice. Early adopters should expect breaking changes.

### 11.2 Stability Tiers

| Tier | Stability | What It Means |
|------|-----------|---------------|
| **Stable** | Production-ready | Breaking changes require MAJOR version bump |
| **Beta** | Feature-complete | May change in MINOR versions with deprecation notice |
| **Experimental** | In development | May change or be removed at any time |

**Current Status (KCP Core v1 alpha)**:

| Component | Tier | Notes |
|-----------|------|-------|
| `.klein` schema | Beta | Core fields stable; extensions may change |
| `.kleinc` container format | Beta | Structure stable; new payload kinds may be added |
| HAIL event schema | Beta | Core events stable; new event kinds may be added |
| `SImgB` / `RImgB` | Beta | Field names stable; new fields may be added |
| ECRP protocol | Beta | Event format stable; strategies may evolve |
| Physics engine (geodesic) | Stable | Algorithm frozen; new solvers added separately |
| Substrate driver protocol | Beta | Core methods stable; sensing API experimental |
| Conformance test vectors | Stable | IDs and expected outputs frozen once released |
| `klein-sim` CLI | Beta | Flags and output format may change |
| `klein-conform` CLI | Beta | Report format may change |

### 11.3 Deprecation Policy

1. **Deprecation Notice**: Deprecated features MUST be documented in CHANGELOG and emit warnings for at least one MINOR version before removal.
2. **Migration Path**: Deprecated features MUST include a documented migration path to the replacement.
3. **Legacy Aliases**: Removed features MAY retain read-only aliases for backwards compatibility (e.g., `DSB` → `SImgB`).

### 11.4 Wire Format Compatibility

**Forward Compatibility**: Implementations SHOULD ignore unknown fields in JSON schemas to allow extension without breaking older parsers.

**Backwards Compatibility**: New required fields MUST NOT be added to existing schemas without a MAJOR version bump. Optional fields with sensible defaults MAY be added in MINOR versions.

### 11.5 Test Vector Contract

Once a test vector is released:
- Its **ID** is permanent and MUST NOT be reused
- Its **expected output** is frozen and MUST NOT change
- Its **purpose** may be clarified but not altered
- New vectors may be added, but existing ones MUST NOT be modified

This ensures that conformance test results are reproducible across protocol versions.

---

## 12. Future Work (Roadmap)

While v1.0 relies on Scalar Impedance and Geodesic Routing, future versions will expand:

### v2.0 Planned Features

- Anisotropic Manifolds: Riemannian Metric Tensors (g_ij) for direction-dependent costs
- Hamiltonian Mode: Coverage Solver for cleaning/sterilization cycles (visit all nodes)

---

## 13. Changelog

| Version | Date | Changes |
|---------|------|---------|
| v0.4 | 2026-01-04 | Added RUNTIME_STATE_SNAPSHOT, ECRP_ATTEMPT, REPLAN_DECISION; capability gating |
| v1.0 | 2026-01-07 | Consolidated HAIL + hardware contract; added fault injection docs; terminology rebrand |

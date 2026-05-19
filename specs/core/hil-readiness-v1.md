# HIL Readiness v1

HIL Readiness v1 defines the interface boundary future hardware-in-the-loop backends must satisfy.

It is an interface/spec layer only. Current alpha may validate contracts and run a mock backend
shape, but it does not connect to physical devices, certify hardware, attest observations, provide
trusted timestamps, or prove physical truth.

## Scope

`CURRENT_ALPHA`:

- HIL backend contract and status schemas.
- Interface validation and mock/dry-run backend behavior.
- Explicit safety and observation source declarations.
- No physical device support and no hardware-backed observation proof.

`TARGET_V1`:

- recorded hardware run format;
- dry-run hardware adapters;
- HIL-L0 interface conformance;
- HIL-L1 observed hardware conformance.

`LONG_HORIZON`:

- attested hardware execution;
- trusted timestamps;
- physical proof under an explicit threat model.

## Required Operations

A HIL-ready backend contract declares support for these operations:

- `connect`
- `disconnect`
- `get_capabilities`
- `get_topology`
- `get_health`
- `apply_frame`
- `read_observation`
- `emergency_stop`
- `reset`
- `export_raw_device_log`

Operation semantics:

- Operations return explicit status; there is no silent success.
- All issued frames must be traceable.
- Observations must declare `source_type`.
- Emergency stop state must be represented and must block future `apply_frame` calls.
- Device health must be explicit.

## Contract Shape

```json
{
  "hil_contract_version": "klein.hil_backend_contract.v1",
  "backend_id": "example_hil_backend",
  "backend_version": "0.0.0",
  "profile": {
    "profile_id": "dmf",
    "profile_version": "v1"
  },
  "supports": {
    "connect": true,
    "disconnect": true,
    "get_capabilities": true,
    "get_topology": true,
    "get_health": true,
    "apply_frame": true,
    "read_observation": true,
    "emergency_stop": true,
    "reset": true,
    "export_raw_device_log": false
  },
  "observation_sources": ["mock_hardware"],
  "attestation": {
    "supported": false,
    "profiles": []
  },
  "safety": {
    "requires_emergency_stop": true,
    "requires_reset": true
  },
  "limitations": [
    "Interface contract only.",
    "No physical device is claimed."
  ]
}
```

## Status Shape

```json
{
  "hil_status_version": "klein.hil_backend_status.v1",
  "backend_id": "example_hil_backend",
  "connected": false,
  "health": "UNKNOWN",
  "emergency_stopped": false,
  "last_error_code": null,
  "details": {}
}
```

`UNKNOWN` is allowed before connection. `FAULTED` must include an error code. `emergency_stopped:
true` must block `apply_frame` in any implementation.

## Forbidden Claims

HIL readiness is not HIL support, hardware certification, physical truth, sensor proof, trusted
timestamping, or hardware attestation.

## Bundle And Manifest Binding

HIL Backend Contract v1 is not required in Run Bundle v1 and is not bound into Run Manifest v1 or
HAIL lifecycle events in current alpha. Recorded Device Run v1 may archive HIL contract/status
snapshots next to a `.kcprun` bundle, but that archival wrapper still does not imply hardware
support. A future bundle profile may allow an optional `hil/hil_contract.json` entry and a strict
verifier mode such as `--require-hil-readiness`, but current alpha keeps HIL readiness validation
independent of execution evidence so no hardware support is implied.

Generic DMF Backend Adapter v1 can wrap this interface in dry-run mode to produce trace, raw-log,
mock observation, and recorded-run artifacts. That adapter skeleton still does not claim HIL
execution or hardware support.

OpenDrop / EWOD Adapter Skeleton v1 may archive the same mock HIL contract/status snapshots in its
recorded-run package. This records adapter boundary readiness only; it is not OpenDrop HIL support,
device control, or physical evidence.

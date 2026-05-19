# Generic DMF Backend Adapter v1

Generic DMF Backend Adapter v1 defines the adapter skeleton future DMF/EWOD backends can implement.

It is a dry-run/skeleton layer in current alpha. It does not connect to physical devices, implement
OpenDrop communication, perform serial/USB/network IO, read real sensors, provide trusted
timestamps, provide hardware attestation, or prove physical truth.

## Scope

`CURRENT_ALPHA`:

- adapter config/status schemas;
- dry-run/mock operation flow;
- runbook-to-command translation skeleton;
- trace/raw-log/mock-observation production;
- mock Recorded Device Run package creation;
- hardware IO explicitly rejected.

`CURRENT_ALPHA` now also includes an OpenDrop/EWOD-specific skeleton layered above this generic
adapter boundary. The OpenDrop skeleton validates OpenDrop-style config/status/command intents and
generates dry-run command intents, but it still does not import an SDK or perform hardware IO.

`TARGET_V1`:

- real HIL backend implementations;
- real OpenDrop/EWOD adapter implementation;
- recorded hardware runs;
- hardware observation source semantics.

`LONG_HORIZON`:

- attested backend execution;
- physical proof under an explicit threat model.

## Responsibilities

A DMF backend adapter is responsible for:

- loading and validating adapter config;
- exposing HIL contract compatibility;
- exposing backend capability declaration compatibility;
- translating KCP Runbook v1 planned steps into backend operations;
- translating DMF frames into adapter command frames;
- producing Execution Trace v1 compatible steps;
- reading mock/simulated observations in current alpha;
- producing Raw Device Log v1 events;
- supporting emergency stop and reset semantics;
- creating Recorded Device Run v1 packages in dry-run/mock mode.

Out of scope:

- physical device connection;
- vendor SDK integration;
- OpenDrop protocol details;
- real sensor readings;
- hardware attestation.

## Config Shape

```json
{
  "adapter_config_version": "klein.dmf_backend_adapter_config.v1",
  "adapter_id": "generic-dmf-dry-run",
  "adapter_kind": "generic_dmf",
  "backend_id": "generic_dmf_dry_run",
  "backend_version": "0.1.0-alpha",
  "profile": {
    "profile_id": "dmf",
    "profile_version": "v1"
  },
  "mode": "dry_run",
  "hardware_io_enabled": false,
  "hil_contract_path": "hil_contract.json",
  "capabilities_path": "backend_capabilities.json",
  "substrate": {
    "substrate_id": "virtual-dmf-16x8",
    "grid_width": 16,
    "grid_height": 8,
    "max_channels": 128
  },
  "safety": {
    "require_estop": true,
    "allow_hardware_io": false
  },
  "limitations": [
    "Dry-run adapter skeleton only.",
    "No physical device IO."
  ]
}
```

Rules:

- `hardware_io_enabled: true` fails current-alpha validation.
- `mode` must be `dry_run` or `mock` in current alpha.
- hardware mode is target/future.
- `safety.require_estop` must be `true`.
- profile must be `dmf/v1`.

## Status Shape

```json
{
  "adapter_status_version": "klein.dmf_backend_adapter_status.v1",
  "adapter_id": "generic-dmf-dry-run",
  "connected": false,
  "hardware_io_enabled": false,
  "health": "UNKNOWN",
  "emergency_stopped": false,
  "last_error_code": null
}
```

`FAULTED` status must include `last_error_code`. An emergency-stopped adapter must reject dry-run
execution until reset.

## Bundle And Manifest Relationship

Adapter config is not part of `.kcprun` and is not bound into Run Manifest v1 in current alpha. A
Recorded Device Run v1 package may archive adapter-derived raw logs and observations, and a future
package profile may include `backend/adapter_config.json`. This pass does not change HAIL lifecycle
events or bundle shape.

# Backend Adapters, HIL, And Recorded Runs

KCP current alpha has adapter boundaries, not hardware support. These layers show where future
hardware backends plug in and how their evidence would be archived.

## Generic DMF Dry-Run Adapter

Generic DMF Backend Adapter v1 validates dry-run config/status artifacts and translates DMF runbook
steps into adapter command frames. It can emit traces, raw mock device logs, simulator/mock
observations, and mock Recorded Device Run packages.

```bash
klein-dmf-backend validate-config tests/fixtures/backends/dmf/generic_dmf_dry_run_config.json
klein-dmf-backend dry-run-runbook --config tests/fixtures/backends/dmf/generic_dmf_dry_run_config.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp-docs/dmf_dry_run
klein-dmf-backend create-mock-recording --config tests/fixtures/backends/dmf/generic_dmf_dry_run_config.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun --output .tmp-docs/dmf_recording
```

## OpenDrop/EWOD Dry-Run Adapter Skeleton

OpenDrop/EWOD Adapter Skeleton v1 validates OpenDrop-style config/status/command-intent artifacts,
maps KCP DMF channels to OpenDrop-style electrodes, and emits dry-run OpenDrop command intents.

```bash
klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
klein-opendrop-backend map-electrodes tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
klein-opendrop-backend dry-run-runbook --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp-docs/opendrop_dry_run
klein-opendrop-backend create-mock-recording --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun --output .tmp-docs/opendrop_recording
```

This is not OpenDrop hardware support. It imports no vendor SDK, opens no serial/USB/network
transport, and produces no physical proof.

## OpenDrop Transport Planning

OpenDrop Transport Planning v1 adds disabled transport config and deterministic command-stream
artifacts for future OpenDrop-style serial integration.

```bash
klein-opendrop-backend validate-transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json
klein-opendrop-backend serialize-runbook --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp-docs/opendrop_commands.jsonl
```

The generated command stream is a dry-run planning artifact only. Current-alpha schemas and runtime
validators both reject `hardware_io_enabled=true`, configured endpoints, baud rates, and serialized
commands marked as hardware-IO allowed. No OpenDrop device IO is performed.

GaudiLabs/OpenDrop is an external open-source project. KCP current alpha does not copy, vendor, or
derive from OpenDrop firmware or controller code. Future hardware integration must review license
compatibility before copying or deriving from GPL-licensed code.

## HIL Readiness

HIL Readiness v1 defines the contract and status shape a future HIL backend must satisfy.

```bash
klein-hil validate-contract tests/fixtures/hil/hil_contract_mock_dmf.json
```

Passing HIL readiness validation means the interface artifact is well-formed. It does not mean a
hardware-in-the-loop run occurred.

## Recorded Device Runs

Recorded Device Run v1 archives `.kcprun` evidence with raw logs, observations, HIL snapshots, and
optional backend metadata.

```bash
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
```

Current alpha recorded runs use `source_type: "mock_hardware"` and `hardware_claimed: false`.

## Future Adapter Progression

The expected progression is:

```text
dry-run adapter skeleton
    -> transport planning and deterministic command streams
    -> real transport prototype
    -> hardware source semantics
    -> sensor observation semantics
    -> trusted timestamp profile
    -> attestation profile
    -> hardware-backed evidence under a threat model
```

Do not treat current adapters as production drivers or hardware certification.

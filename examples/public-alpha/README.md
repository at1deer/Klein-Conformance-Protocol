# KCP Public Alpha Demo

This demo package shows the current KCP alpha in the smallest public-friendly path:

1. verify the authoritative v1 conformance suite;
2. verify a portable `.kcprun` bundle;
3. validate a mock/dry-run Recorded Device Run archive;
4. validate OpenDrop/EWOD dry-run and transport-planning artifacts;
5. run the Rust cross-language verifier.

The demo references existing repository fixtures instead of duplicating them, so it stays aligned
with tests and validation.

## Canonical Demo Assets

- Demo bundle: `tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun`
- Demo recorded run: `tests/fixtures/recorded_run/opendrop_dry_run_recorded_run`
- OpenDrop dry-run config: `tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json`
- OpenDrop transport planning config: `tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json`
- OpenDrop command stream fixture: `tests/fixtures/backends/dmf/opendrop/command_stream_minimal.jsonl`
- Cross-language fixture index: `tests/fixtures/cross_language/fixtures.json`
- Rust verifier source: `verifiers/rust/`

All bundled keys and signing material used by the fixture suite are public test fixtures only. They
are not production credentials.

Use `klein-export-clean-repo` for release handoff archives; do not upload raw working-tree zips.

KCP does not copy or vendor GaudiLabs/OpenDrop firmware or controller code. Any future OpenDrop
hardware integration requires explicit license compatibility review before copying or deriving from
GPL-licensed code.

## Demo Docs

- `examples/public-alpha/DEMO_COMMANDS.md`
- `examples/public-alpha/EXPECTED_OUTPUTS.md`
- `examples/public-alpha/VALIDATION_TRANSCRIPT.md`

## Non-Claims

This public alpha verifies evidence artifacts, signatures, bundles, fixtures, simulated runs, and
mock/dry-run adapter outputs. It does not prove physical execution and does not claim hardware
support, HIL execution, sensor proof, timestamp proof, hardware attestation proof, TPM/TEE verification, real OpenDrop control,
or production certification.

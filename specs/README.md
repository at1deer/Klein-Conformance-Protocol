# Specs Index

This directory contains the current KCP protocol, artifact, profile, algorithm, and catalog specs.
The split v1 specs are the public-alpha reference.

## Core Specs

Current alpha implemented:

- `specs/core/kcp-core-v1.md`
- `specs/core/hail-v1.md`
- `specs/core/hail-digest-chain-v1.md`
- `specs/core/execution-modes-v1.md`
- `specs/core/conformance-report-v1.md`
- `specs/core/error-codes-v1.md`
- `specs/core/run-manifest-v1.md`
- `specs/core/trust-policy-v1.md`
- `specs/core/backend-identity-registry-v1.md`
- `specs/core/backend-capability-declaration-v1.md`
- `specs/core/conformance-levels-v1.md`
- `specs/core/run-bundle-v1.md`
- `specs/core/independent-verifier-v1.md`
- `specs/core/runbook-v1.md`
- `specs/core/execution-trace-v1.md`
- `specs/core/ecrp-v1.md`
- `specs/core/observation-v1.md`
- `specs/core/hil-readiness-v1.md`
- `specs/core/recorded-device-run-v1.md`
- `specs/core/trusted-timestamp-profile-v1.md`
- `specs/core/attestation-profile-v1.md`

Target/future boundary specs:

- `specs/core/substrate-driver-boundary-v1.md`

## Artifact Specs

Current alpha implemented:

- `specs/artifacts/klein-project-v1.md`
- `specs/artifacts/klein-container-v1.md`
- `specs/artifacts/simgb-v1.md`
- `specs/artifacts/rimgb-v1.md`
- `specs/artifacts/trace-v1.md`

## Profile Specs

Current alpha implemented:

- `specs/profiles/dmf/dmf-core-v1.md`
- `specs/profiles/dmf/dmf-ewod-v1.md`
- `specs/profiles/dmf/dmf-backend-adapter-v1.md`
- `specs/profiles/dmf/opendrop-ewod-adapter-v1.md`
- `specs/profiles/dmf/opendrop-transport-planning-v1.md`

Additional profile context:

- `specs/profiles/dmf/dmf-opendrop-v1.md`

## Algorithms

- `specs/algorithms/klein_canon.jsonl.v1.md`

## Catalogs

- `specs/catalogs/conformance_levels.v1.json`: normative conformance-level catalog.
- `src/klein/catalogs/conformance_levels.v1.json`: packaged copy used by installed CLIs.

## Claim Layers

- `CURRENT_ALPHA`: implemented and tested in this repository today.
- `TARGET_V1`: required before stronger KCP Core v1 claims are fully defensible.
- `LONG_HORIZON`: TCP/IP-for-matter goals such as hardware-backed evidence under a threat model.

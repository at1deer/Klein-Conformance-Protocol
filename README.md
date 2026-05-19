# Klein Conformance Protocol (KCP)

KCP is a protocol stack for producing, packaging, signing, and independently verifying evidence of
physical-substrate execution attempts under uncertainty. It is aimed at making heterogeneous programmable-matter substrates describable, testable, and comparable without pretending physical execution is deterministic.

## Current Alpha Status

This repository is a public alpha for the KCP core evidence and execution stack.

- **KCP Core Evidence/Execution Alpha**: artifacts, runbooks, traces, HAIL evidence, hash chains,
  signed manifests, `.kcprun` bundles, and independent verification.
- **DMF/EWOD Simulator Profile Alpha**: digital microfluidics payload validation, frame conversion,
  simulator-backed observation, and one simulator-only recovery-success path.
- **HIL readiness and adapter skeletons only**: HIL contracts, Recorded Device Run archives, generic
  DMF dry-run adapters, OpenDrop/EWOD dry-run adapter skeletons, and disabled OpenDrop transport
  planning artifacts.
- **Trusted Timestamp Profile Stub v1**: schema, mock/local token fixtures, target-hash binding
  checks, and status vocabulary without trusted timestamp proof.
- **Attestation Profile Stub v1**: schema, none/mock statement fixtures, subject/backend binding
  checks, and status vocabulary without hardware attestation proof.

The current alpha verifies evidence artifacts and declared bindings. It does not prove physical
execution.

## What KCP Currently Does

- validates `.klein` Project v1 and `.kleinc` Container v1 artifacts;
- builds Runbook v1 plans and Execution Trace v1 records;
- emits and validates HAIL v1 execution evidence;
- computes canonical JSON/JCS digests and HAIL chain digests;
- signs Run Manifest v1 evidence with Ed25519 test fixtures;
- verifies Trust Policy v1, Backend Identity Registry v1, signed registry provenance, and signed
  Backend Capability Declaration v1 fixtures;
- packages portable `.kcprun` Run Bundle v1 archives;
- verifies bundles through Python and Rust independent verifier surfaces;
- provides DMF/EWOD profile alpha validation and simulator execution;
- supports simulator-backed ECRP recovery evidence and Observation v1 snapshots;
- defines HIL Readiness v1 contracts/statuses and Recorded Device Run v1 archives;
- provides Generic DMF and OpenDrop/EWOD dry-run adapter skeletons plus OpenDrop transport planning;
- validates mock/local timestamp profiles and tokens with `klein-timestamp`.

## What KCP Does Not Claim

Current alpha does not claim:

- hardware support;
- HIL execution;
- physical truth proof;
- real sensor proof or sensor attestation;
- trusted timestamp proof or external timestamp authority verification;
- hardware attestation proof or TPM/TEE verification;
- real OpenDrop control;
- OpenDrop serial hardware transport;
- production certification.

These are not abandoned goals, tracked as `TARGET_V1` or `LONG_HORIZON` work in
`docs/CLAIMS_LEDGER.md`, `docs/CURRENT_ALPHA.md`, and `docs/ROADMAP.md`.

For the current public-alpha synthesis, read `docs/WHITEPAPER.md`.
For a runnable public demo path, start with `examples/public-alpha/README.md`.

## Quickstart

Install the editable package with development and crypto extras:

```bash
python -m pip install -e .[dev,crypto]
```

Run the core test and verification path:

```bash
python -m pytest -q
klein-conform --suite tests/vectors/v1 --backend full_simulator --json
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

See `docs/QUICKSTART.md` for a runnable command tour covering artifacts, runbooks, ECRP,
observations, HIL contracts, recorded runs, DMF adapters, OpenDrop dry-runs, OpenDrop transport
planning fixtures, timestamp and attestation stub fixtures, and Rust verifier fixtures.

## Core Concepts

KCP separates planned execution, observed execution evidence, signed claims, and verification:

```text
.klein/.kleinc
    -> Runbook
    -> Execution Trace
    -> HAIL
    -> Run Manifest
    -> .kcprun Bundle
    -> Independent Verifier
```

The purpose is to make execution attempts, constraints, evidence, and failures explicit enough that independent tools can evaluate the claim.

## Trust Stack

KCP alpha includes a local/test trust stack for evidence verification:

```text
Backend Key
    -> Backend Identity Registry
    -> Signed Registry Provenance
    -> Trust Policy
    -> Signed Backend Capabilities
    -> Verified Run Claim
```

This is not global PKI and not hardware attestation. It is the current machinery for making local
test evidence claims explicit and independently checkable.

`tests/fixtures/crypto/backend_test_ed25519_private.pem` is an intentional public deterministic test
fixture key only. It must not be used for production signing or backend identity.

## DMF/EWOD Profile

The first concrete substrate profile is digital microfluidics / EWOD. Current alpha includes:

- capability/topology-driven payload validation;
- `CHANNEL_LIST`, `FRAME_SEQUENCE`, and `BITMAP_SEQUENCE` payload support;
- sparse, bitmap, and delta frame handling;
- simulator-backed observations;
- simulator-only recovery evidence;
- generic and OpenDrop/EWOD dry-run adapter skeletons.

Read `docs/DMF_PROFILE.md` for the reader-facing overview and `specs/profiles/dmf/` for normative
profile details.

## HIL, Recorded Runs, And Adapters

HIL Readiness v1 defines contracts and status shapes that future hardware backends must satisfy.
Recorded Device Run v1 defines how a run archive can wrap `.kcprun` evidence together with raw logs,
observations, and HIL snapshots. The generic DMF and OpenDrop/EWOD adapters exercise this boundary in
dry-run/mock mode only.

OpenDrop/EWOD adapter skeleton means: this is where an OpenDrop-style backend would plug in. OpenDrop
Transport Planning v1 adds disabled transport configs and deterministic command streams. Neither
means KCP currently controls OpenDrop hardware.

KCP does not copy or vendor GaudiLabs/OpenDrop firmware or controller code. Any future OpenDrop
hardware integration requires explicit license compatibility review before copying or deriving from
GPL-licensed code.

Read `docs/ADAPTERS.md` and `docs/VERIFY_A_BUNDLE.md` for the current boundaries.

## Roadmap

Near-term work is public-alpha documentation, whitepaper rewrite, website/demo prep, and release
packaging. Protocol work after that is expected to move from the timestamp and attestation profile
stubs toward external timestamp authority validation, real attestation verification, real backend
planning, hardware source semantics, and eventually hardware-backed evidence under an explicit threat
model.

See `docs/ROADMAP.md`.

## Repository Layout

- `src/klein/`: Python reference implementation and CLIs.
- `schemas/`: JSON Schemas for protocol artifacts and profile artifacts.
- `specs/`: split protocol, artifact, profile, algorithm, and catalog specs.
- `tests/vectors/v1/`: authoritative v1 conformance vectors.
- `tests/fixtures/`: cross-language, verifier, profile, adapter, and recorded-run fixtures.
- `verifiers/rust/`: first non-Python independent verifier slice.
- `docs/`: public-alpha guides, claims, roadmap, and validation docs.

## Development Validation Matrix

The current public-alpha validation matrix is documented in `docs/VALIDATION_MATRIX.md`. The short
form is:

```bash
python -m compileall -q src tests
python -m pytest -q
ruff check src/klein/hail src/klein/profiles src/klein/tools src/klein/conformance src/klein/crypto src/klein/verifier src/klein/bundle src/klein/artifacts src/klein/execution src/klein/hil src/klein/recording src/klein/backends src/klein/timestamping src/klein/attestation tests/test_hail_core.py tests/test_schema_parity.py
klein-conform --suite tests/vectors/v1 --check-suite-integrity
klein-conform --suite tests/vectors/v1 --backend full_simulator --json
klein-conform --suite tests/vectors/v1 --category negative --backend full_simulator --json
klein-regen-v1-goldens --suite tests/vectors/v1 --backend full_simulator --check
klein-timestamp validate-profile tests/fixtures/timestamp/profile_mock_local.json
klein-timestamp validate-token tests/fixtures/timestamp/token_mock_bundle.json
klein-attestation validate-profile tests/fixtures/attestation/profile_mock_none.json
klein-attestation validate-statement tests/fixtures/attestation/statement_mock_backend.json
klein-conformance-levels validate-catalog
cargo test --manifest-path verifiers/rust/Cargo.toml
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
```

Legacy experimental vectors remain report-only and are not authoritative KCP Core v1 conformance.

The Rust verifier currently requires a recent stable Rust toolchain (validated with
`cargo 1.95.0`). The Ubuntu 24.04 distro-packaged `cargo 1.75` is too old for the committed
`Cargo.lock` (lockfile v4) and `edition2024` dependencies; use [`rustup`](https://rustup.rs/)
or an equivalent current toolchain. See `verifiers/rust/README.md` for details.

# Klein Conformance Protocol

KCP is a public-alpha protocol stack for packaging, signing, and independently verifying evidence of
physical-substrate execution attempts under uncertainty.

## What It Is

KCP separates artifacts, runbooks, traces, HAIL evidence, signed manifests, portable `.kcprun`
bundles, local trust policy, backend identity, backend capabilities, and independent verification.

The goal is a TCP/IP-for-matter evidence layer: execution attempts should be describable,
auditable, portable, and independently checkable across declared substrate profiles.

## What Works Now

- `.klein` and `.kleinc` artifact validation.
- Runbook v1 and Execution Trace v1.
- HAIL v1 evidence and HAIL chain digests.
- Signed Run Manifest v1.
- Trust Policy v1, Backend Identity Registry v1, signed registry provenance, and signed backend
  capabilities.
- `.kcprun` Run Bundle v1 verification.
- Python independent verifier and Rust verifier slice.
- DMF/EWOD simulator profile alpha.
- ECRP simulated recovery evidence and Observation v1 simulator snapshots.
- HIL readiness and Recorded Device Run archive formats.
- Generic DMF and OpenDrop/EWOD dry-run adapter skeletons plus disabled OpenDrop transport planning.

## What It Does Not Claim

Current alpha does not claim hardware support, HIL execution, physical truth, sensor proof,
timestamp proof, hardware attestation proof, TPM/TEE verification, real OpenDrop control, or production certification.

## Try The Demo

Verify a portable bundle:

```bash
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

Validate a recorded-run archive:

```bash
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
```

Validate the OpenDrop dry-run / transport-planning boundary:

```bash
klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
klein-opendrop-backend validate-transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json
```

Run the Rust verifier fixtures:

```bash
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
```

## Read More

- `docs/WHITEPAPER.md`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/VERIFY_A_BUNDLE.md`
- `docs/DMF_PROFILE.md`
- `docs/ADAPTERS.md`
- `docs/ROADMAP.md`
- `examples/public-alpha/README.md`

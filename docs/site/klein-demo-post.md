# KCP Public Alpha Demo

Klein Conformance Protocol now has a public-alpha demo path for verifying portable evidence
packages without running the simulator.

The demo centers on one `.kcprun` bundle:

```bash
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

That command checks bundle integrity, HAIL canonicalization, lifecycle evidence, signatures, trust
policy, backend identity, signed registry provenance, backend capabilities, and conformance-level
claims. It is evidence verification, not physical proof.

The demo also validates a mock/dry-run Recorded Device Run archive:

```bash
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
```

And it validates the OpenDrop/EWOD dry-run and transport-planning boundary:

```bash
klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
klein-opendrop-backend validate-transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json
```

For independent implementation confidence, the Rust verifier consumes the same cross-language
fixture index:

```bash
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
```

Current alpha includes a substantial evidence stack: artifacts, runbooks, traces, HAIL, signed
manifests, bundles, local trust policy, backend registries, signed capabilities, DMF/EWOD simulator
profile, observations, HIL readiness, recorded-run archives, dry-run adapter skeletons, and disabled
OpenDrop transport planning.

It does not claim hardware support, HIL execution, physical truth, sensor proof, timestamp proof,
hardware attestation proof, TPM/TEE verification, real OpenDrop control, or production certification. Those remain target and
future work.

Start with `examples/public-alpha/DEMO_COMMANDS.md`, then read `docs/WHITEPAPER.md` for the current
architecture and claims.

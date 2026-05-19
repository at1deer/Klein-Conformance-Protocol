# Conformance vs Verification

Klein separates conformance execution from independent evidence verification.

## Conformance Runner

The conformance runner executes or simulates vectors, compares emitted HAIL against goldens, and helps backend/profile implementers test behavior.

It may:

- run the reference simulator
- read vector metadata
- compare output to expected goldens
- classify positive and negative vector outcomes

## Independent Verifier

The independent verifier does not execute or simulate. It consumes a `.kcprun` bundle or bundle directory and validates protocol/cryptographic consistency.

It checks:

- bundle structure and hashes
- HAIL validation, canonicalization, lifecycle, and chain
- Run Manifest v1 payload binding and Ed25519 signature
- optional Backend Identity Registry v1 identity resolution
- optional signed registry provenance and backend key lifecycle checks
- optional signed backend capability declaration checks
- optional conformance-level catalog and dependency checks for declared capability levels
- DMF/EWOD profile schema/runtime checks for simulator capability and payload claims
- optional Runbook v1 / Execution Trace v1 hash and step-comparison fixtures where supplied
- Trust Policy v1 authorization
- optional conformance report agreement

The Python reference surface is `klein-verify-bundle`. The first non-Python slice is `verifiers/rust`,
which consumes public cross-language fixtures and `.kcprun` bundles without importing Python
simulator or conformance code. Its JSON output validates against the Independent Verifier result
schema for the core bundle path, and parity tests compare the core bindings/checks against Python.

## Important Cases

- A backend can fail conformance.
- A bundle can verify internally even if it represents an explicit failed run.
- A signed-conformant failed run is still valid evidence of explicit failure.
- A Runbook v1 is planned execution, while an Execution Trace v1 is the issued/applied path; HAIL
  remains the canonical evidence log.
- Verification is not physical truth.

Hardware attestation, trusted timestamps, real-world sensor validity, substrate attestation, and physical proof remain future work.

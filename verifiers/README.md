# Independent Verifiers

This directory contains non-Python verifier implementations for the language-neutral Klein verifier contract.

These verifiers consume public cross-language fixtures and portable `.kcprun` bundles. They must not import the Python simulator, conformance runner, vector harness, or golden regeneration code.

Verifier success means the packaged evidence and trust bindings are valid under current alpha rules.
It does not prove physical execution, hardware sensor truth, trusted timestamps, or hardware
attestation.

Current implementations:

- `rust/`: Rust verifier slice for Canonical JSON/JCS, HAIL Chain v1, Run Manifest Ed25519 signatures, Backend Identity Registry v1 resolution, Trust Policy v1 authorization, `.kcprun` bundle hash/safety checks, and `klein.independent_verifier_result.v1` JSON output.

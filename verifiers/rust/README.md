# Klein Rust Verifier

`klein-verifier-rs` is the first non-Python independent verifier slice for Klein.

It validates the cross-language fixture index and verifies a portable `.kcprun` bundle without executing the simulator or using Python conformance runner state.

Implemented checks:

- RFC 8785/JCS canonical JSON for Klein fixture values
- HAIL JSONL canonical digest and HAIL Chain v1 digest
- Run Manifest v1 Ed25519 signature verification
- Backend Identity Registry v1 fixture and bundle resolution
- signed Backend Identity Registry v1 provenance checks against local Trust Policy authority roots
- Backend Capability Declaration v1 signature, trust, DMF validity, run-scope, and bundle checks
- Conformance Levels Matrix v1 fixture checks for known levels, future-level rejection, and dependency closure
- DMF/EWOD capability fixture checks for basic ranges and supported/unsupported frame format consistency
- DMF/EWOD payload fixture shape checks for channel-list, sparse frame, and unsupported rle cases
- `.klein`/`.kleinc` artifact canonical hash fixtures and simple artifact schema error fixtures
- Runbook v1 and Execution Trace v1 canonical hash fixtures plus simple trace/runbook step comparison
- ECRP Retry/Replan Contract v1 policy shape, HAIL attempt-count/terminal-failure fixtures, and
  simple trace failure-evidence fixtures
- simulator-only ECRP recovery success fixtures that check policy-approved `NUDGE_PULSE` retry
  evidence without simulating hardware recovery
- Observation v1 simulator snapshot fixtures, simple policy checks, canonical hash checks, and trace
  alignment checks without claiming hardware observation
- HIL Readiness v1 contract/status fixture checks without claiming HIL execution or hardware support
- Recorded Device Run v1 and Raw Device Log v1 fixture checks without claiming hardware-backed evidence
- Generic DMF Backend Adapter v1 config/status fixture checks without implementing a Rust adapter
- OpenDrop/EWOD Adapter Skeleton v1 config/status/command-intent fixture checks without implementing a Rust adapter or claiming OpenDrop hardware IO
- OpenDrop Transport Planning v1 config, serial-command, and command-stream fixture checks without
  implementing serialization or serial IO in Rust
- Trusted Timestamp Profile v1 stub fixture checks for mock/local profiles and tokens without
  claiming trusted timestamp proof or TSA validation
- Attestation Profile v1 stub fixture checks for none/mock profiles and statements without claiming
  TPM/TEE verification or hardware attestation proof
- Trust Policy v1 key/scope authorization
- `.kcprun` zip member safety and bundle entry SHA-256 hashes
- `klein.independent_verifier_result.v1` JSON output for bundle verification

Run it from the repository root:

```bash
cargo test --manifest-path verifiers/rust/Cargo.toml
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-bundle tests/fixtures/run_bundle/valid_signed_run.kcprun
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-bundle tests/fixtures/run_bundle/valid_signed_run.kcprun --json
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_registry.kcprun
```

Bundle security behavior matches the Python reference posture for the checked cases: path traversal, absolute paths, duplicate members, missing declared entries, undeclared files, hash mismatches, and unsupported formats are rejected.

Trust Policy v1 behavior is tested for trusted scope, wrong backend/profile scope, revoked keys, unknown keys, and missing policy. Bundle verification currently requires a bundled trust policy; no-policy manifest-only verification is not a supported Rust mode.

Backend Identity Registry v1 behavior is tested for valid identity resolution, signed registry provenance, missing backend, key mismatch, revoked keys, and registry-backed bundle verification. Registry resolution is not global PKI or hardware attestation.

This implementation is intentionally narrow: it is not a simulator, not a conformance runner, not a
TSA/RFC 3161 verifier, not a TPM/TEE quote verifier, and not a physical truth or hardware
attestation system.

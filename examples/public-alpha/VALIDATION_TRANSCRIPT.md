# Public Alpha Validation Transcript

Current as of this alpha release-candidate prep pass. Counts may change after future protocol work.

## Environment

```text
Python 3.12.10
cargo 1.95.0 (f2d3ce0bd 2026-03-21)
```

## Python Validation

```text
python -m compileall -q src tests
[exit_code=0]

python -m pytest -q
439 passed, 3 skipped

ruff check ...
All checks passed!
```

## V1 Conformance

```text
klein-conform --suite tests/vectors/v1 --check-suite-integrity
Suite integrity ok: tests\vectors\v1

klein-conform --suite tests/vectors/v1 --backend full_simulator --json
total: 53
passed: 53
failed: 0
errors: 0
```

## V1 Negative Conformance

```text
klein-conform --suite tests/vectors/v1 --category negative --backend full_simulator --json
total: 32
passed: 32
failed: 0
errors: 0
```

## Goldens

```text
klein-regen-v1-goldens --suite tests/vectors/v1 --backend full_simulator --check
[exit_code=0]
```

Existing HAIL goldens did not change.

## Catalog And Bundle

```text
klein-conformance-levels validate-catalog
Conformance level catalog valid: 39 levels

klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
Independent verifier: overall_status=pass format=zip
```

## Timestamp Stub

```text
klein-timestamp validate-profile tests/fixtures/timestamp/profile_mock_local.json
valid mock/local timestamp artifact; trusted_time_claimed=false; no trusted timestamp proof

klein-timestamp validate-token tests/fixtures/timestamp/token_mock_bundle.json
valid mock/local timestamp artifact; trusted_time_claimed=false; no trusted timestamp proof
```

## Attestation Stub

```text
klein-attestation validate-profile tests/fixtures/attestation/profile_mock_none.json
valid mock/null attestation artifact; hardware_attestation_claimed=false; no hardware attestation proof

klein-attestation validate-statement tests/fixtures/attestation/statement_mock_backend.json
valid mock/null attestation artifact; hardware_attestation_claimed=false; no hardware attestation proof
```

## Clean Export And Package Build

```text
klein-export-clean-repo --output klein-conformance-clean.zip --dry-run
[exit_code=0]

python -m build
Successfully built klein_protocol-1.0.0a0.tar.gz and klein_protocol-1.0.0a0-py3-none-any.whl

twine check dist/*
Checking dist\klein_protocol-1.0.0a0-py3-none-any.whl: PASSED
Checking dist\klein_protocol-1.0.0a0.tar.gz: PASSED
```

## Recorded Run And OpenDrop Dry-Run Config

```text
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
Recorded Device Run valid: tests\fixtures\recorded_run\opendrop_dry_run_recorded_run

klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
OpenDrop/EWOD dry-run skeleton config valid: hardware_io_enabled=false; no physical execution

klein-opendrop-backend validate-transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json
OpenDrop transport planning config valid: hardware_io_enabled=false; serialized command stream only; no device IO performed

klein-opendrop-backend serialize-runbook --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output /tmp/opendrop_commands.jsonl
OpenDrop dry-run command stream serialized from runbook: \tmp\opendrop_commands.jsonl
serialized command stream only; hardware_io_enabled=false; no device IO performed
```

## Rust Verifier

```text
cargo test --manifest-path verifiers/rust/Cargo.toml
test result: ok

cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
Klein Rust verifier: 106 fixtures passed, 0 failed

cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
Klein Rust bundle verifier: pass trusted_key_ids=klein-test-backend-001
```

## Legacy Report-Only Corpus

```text
klein-conform --suite tests/vectors --legacy --backend full_simulator --json
total: 120
passed: 2
failed: 118
errors: 0
exit_code: 1
```

The legacy corpus is report-only migration material. Exit code `1` is expected.

## Non-Claims

This transcript validates current-alpha evidence and demo workflows. It does not claim hardware
support, HIL execution, physical truth, sensor proof, timestamp proof, hardware attestation proof,
TPM/TEE verification, real OpenDrop control, or production certification.

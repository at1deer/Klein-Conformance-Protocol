# Expected Public Alpha Outputs

These snippets reflect the current public alpha. Counts may change after future protocol work.

## Core V1 Conformance

Command:

```bash
klein-conform --suite tests/vectors/v1 --backend full_simulator --json
```

Expected summary:

```text
53 total
53 passed
0 failed
0 errors
```

## V1 Negative Conformance

Command:

```bash
klein-conform --suite tests/vectors/v1 --category negative --backend full_simulator --json
```

Expected summary:

```text
32 total
32 passed
0 failed
0 errors
```

## Bundle Verifier

Command:

```bash
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

Expected snippet:

```text
Independent verifier: overall_status=pass format=zip
```

## Conformance Level Catalog

Command:

```bash
klein-conformance-levels validate-catalog
```

Expected snippet:

```text
Conformance level catalog valid: 39 levels
```

## Timestamp Stub

Command:

```bash
klein-timestamp validate-token tests/fixtures/timestamp/token_mock_bundle.json
```

Expected snippet:

```text
valid mock/local timestamp artifact; trusted_time_claimed=false; no trusted timestamp proof
```

## Attestation Stub

Command:

```bash
klein-attestation validate-statement tests/fixtures/attestation/statement_mock_backend.json
```

Expected snippet:

```text
valid mock/null attestation artifact; hardware_attestation_claimed=false; no hardware attestation proof
```

## Recorded Run

Command:

```bash
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
```

Expected snippet:

```text
Recorded Device Run valid: tests\fixtures\recorded_run\opendrop_dry_run_recorded_run
```

The archive is mock/dry-run current-alpha evidence and has `hardware_claimed: false`.

## OpenDrop Config

Command:

```bash
klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
```

Expected snippet:

```text
OpenDrop/EWOD dry-run skeleton config valid: hardware_io_enabled=false; no physical execution
```

## OpenDrop Transport Planning

Command:

```bash
klein-opendrop-backend validate-transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json
```

Expected:

```text
OpenDrop transport planning config valid: hardware_io_enabled=false; serialized command stream only; no device IO performed
```

## OpenDrop Command Stream

Command:

```bash
klein-opendrop-backend serialize-runbook --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp/opendrop_commands.jsonl
```

Expected:

```text
OpenDrop dry-run command stream serialized from runbook: .tmp\opendrop_commands.jsonl
serialized command stream only; hardware_io_enabled=false; no device IO performed
```

## OpenDrop Dry-Run

Command:

```bash
klein-opendrop-backend dry-run-runbook --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp/opendrop_dry_run
```

Expected snippet:

```text
OpenDrop/EWOD dry-run skeleton complete: .tmp\opendrop_dry_run
hardware_io_enabled=false; no physical execution
```

## Rust Toolchain Requirement

The Rust verifier currently requires a recent stable Rust toolchain (validated with
`cargo 1.95.0`). The Ubuntu 24.04 distro-packaged `cargo 1.75` is too old for the committed
`Cargo.lock` (lockfile v4) and `edition2024` dependencies. Use [`rustup`](https://rustup.rs/)
or an equivalent current toolchain. See [`../../verifiers/rust/README.md`](../../verifiers/rust/README.md).

## Rust Fixtures

Command:

```bash
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
```

Expected snippet:

```text
Klein Rust verifier: 106 fixtures passed, 0 failed
```

## Rust Bundle Verifier

Command:

```bash
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

Expected snippet:

```text
Klein Rust bundle verifier: pass trusted_key_ids=klein-test-backend-001
```

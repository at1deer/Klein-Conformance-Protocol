# Public Alpha Demo Commands

Run these commands from the repository root.

On Windows PowerShell, the commands work as written. The OpenDrop dry-run writes into `.tmp`; create
that directory first if it does not exist.

## 1. Install

```bash
python -m pip install -e .[dev,crypto]
```

## 2. Verify The Core V1 Conformance Suite

```bash
klein-conform --suite tests/vectors/v1 --backend full_simulator --json
```

## 3. Verify Negative Vectors

```bash
klein-conform --suite tests/vectors/v1 --category negative --backend full_simulator --json
```

## 4. Verify A Portable `.kcprun` Bundle

```bash
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

## 5. Verify A Recorded Device Run Archive

```bash
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
```

## 6. Validate OpenDrop Dry-Run Adapter Config

```bash
klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
```

## 7. Validate OpenDrop Transport Planning

```bash
klein-opendrop-backend validate-transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json
```

This validates a disabled transport planning artifact only. It does not perform OpenDrop hardware IO.

## 8. Serialize OpenDrop Dry-Run Command Stream

```bash
python -c "from pathlib import Path; Path('.tmp').mkdir(exist_ok=True)"
klein-opendrop-backend serialize-runbook --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp/opendrop_commands.jsonl
```

## 9. Run OpenDrop Dry-Run

```bash
python -c "from pathlib import Path; Path('.tmp').mkdir(exist_ok=True)"
klein-opendrop-backend dry-run-runbook --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp/opendrop_dry_run
```

## 8. Rust Verifier

Requires a recent stable Rust toolchain (validated with `cargo 1.95.0`). The Ubuntu 24.04
distro-packaged `cargo 1.75` is too old for this crate's `Cargo.lock` v4 and `edition2024`
dependencies; use [`rustup`](https://rustup.rs/) or an equivalent current toolchain. See
[`verifiers/rust/README.md`](../../verifiers/rust/README.md) for details.

```bash
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

## Cleanup

The generated demo outputs are `.tmp/opendrop_commands.jsonl` and `.tmp/opendrop_dry_run`. They are
safe to delete.

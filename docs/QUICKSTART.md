# Quickstart

Run these commands from the repository root after cloning the repo. On Windows PowerShell, replace
line continuations with a single line if needed. The examples use repo-local output directories under
`.tmp-docs/` so they work on Windows, macOS, and Linux.

For a shorter public demo script, see `examples/public-alpha/DEMO_COMMANDS.md`.

## 1. Install Editable Package

```bash
python -m pip install -e .[dev,crypto]
```

Create a repo-local scratch directory for generated outputs:

```bash
python -c "from pathlib import Path; Path('.tmp-docs').mkdir(exist_ok=True)"
```

## 2. Run Core Tests

```bash
python -m pytest -q
```

Expected at this point: about `439 passed, 3 skipped`. Counts may change as the repo evolves.

## 3. Run V1 Conformance

```bash
klein-conform --suite tests/vectors/v1 --backend full_simulator --json
```

Expected at this point: `53 total`, `53 passed`, `0 failed`.

## 4. Verify A `.kcprun` Bundle

```bash
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

This verifies packaged evidence and trust bindings. It does not prove physical execution.

## 5. Inspect Conformance Levels

```bash
klein-conformance-levels validate-catalog
```

Expected at this point: `39 levels`.

## 6. Validate An Artifact

```bash
klein-artifact validate tests/vectors/v1/core/001_hard_minimal_project/input/project.klein
klein-artifact hash tests/vectors/v1/core/002_hard_minimal_container/input/container.kleinc
```

## 7. Build A Runbook

```bash
klein-runbook build --artifact tests/vectors/v1/core/002_hard_minimal_container/input/container.kleinc --output .tmp-docs/runbook.json
```

The output is a Runbook v1 planning artifact, not execution proof.

## 8. Validate ECRP Recovery Fixture

```bash
klein-ecrp validate-policy tests/fixtures/ecrp/policy_simulated_recovery_success.json
klein-ecrp validate-trace --trace tests/fixtures/ecrp/trace_simulated_recovery_success.json --runbook tests/fixtures/ecrp/runbook_simulated_recovery_success.json --policy tests/fixtures/ecrp/policy_simulated_recovery_success.json
```

This checks simulator-only recovery evidence.

## 9. Validate Observation Fixture

```bash
klein-observation validate-snapshot tests/fixtures/observation/observation_simulated_dmf.json
```

This validates simulator-backed observation shape and binding. It is not hardware sensor proof.

## 10. Validate HIL Contract

```bash
klein-hil validate-contract tests/fixtures/hil/hil_contract_mock_dmf.json
```

This validates HIL readiness interface shape. It is not HIL execution.

## 11. Validate Recorded Run

```bash
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
```

This validates a mock/dry-run recorded-run package.

## 12. Run Generic DMF Dry-Run Adapter

```bash
klein-dmf-backend validate-config tests/fixtures/backends/dmf/generic_dmf_dry_run_config.json
klein-dmf-backend dry-run-runbook --config tests/fixtures/backends/dmf/generic_dmf_dry_run_config.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp-docs/dmf_dry_run
```

## 13. Run OpenDrop Dry-Run Adapter

```bash
klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
klein-opendrop-backend map-electrodes tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
klein-opendrop-backend dry-run-runbook --config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json --runbook tests/fixtures/execution/runbook_minimal_dmf.json --output .tmp-docs/opendrop_dry_run
```

The OpenDrop adapter is a dry-run/config-only skeleton. It does not control OpenDrop hardware.

## 14. Validate Timestamp Stub Fixtures

```bash
klein-timestamp validate-profile tests/fixtures/timestamp/profile_mock_local.json
klein-timestamp validate-token tests/fixtures/timestamp/token_mock_bundle.json
```

This validates mock/local timestamp artifacts. It is not trusted timestamp proof.

## 15. Validate Attestation Stub Fixtures

```bash
klein-attestation validate-profile tests/fixtures/attestation/profile_mock_none.json
klein-attestation validate-statement tests/fixtures/attestation/statement_mock_backend.json
```

This validates none/mock attestation artifacts. It is not hardware attestation proof.

## 16. Run Rust Verifier Fixtures

```bash
cargo test --manifest-path verifiers/rust/Cargo.toml
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

Expected fixture count at this point: `106 fixtures passed, 0 failed`.

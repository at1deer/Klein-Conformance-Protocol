# Validation Matrix

This matrix documents the public-alpha validation commands. Counts are current for this pass and may
change as fixtures or tests are added.

## Python Validation

```bash
python --version
python -m pip install -e .[dev,crypto]
python -m compileall -q src tests
python -m pytest -q
ruff check src/klein/hail src/klein/profiles src/klein/tools src/klein/conformance src/klein/crypto src/klein/verifier src/klein/bundle src/klein/artifacts src/klein/execution src/klein/hil src/klein/recording src/klein/backends src/klein/timestamping src/klein/attestation tests/test_hail_core.py tests/test_schema_parity.py
```

Expected at this point:

- Python: `3.12.10` in the validated environment.
- Pytest: `439 passed, 3 skipped`.
- Ruff: `All checks passed!`.

## Timestamp Stub Validation

```bash
klein-timestamp validate-profile tests/fixtures/timestamp/profile_mock_local.json
klein-timestamp validate-token tests/fixtures/timestamp/token_mock_bundle.json
klein-timestamp verify-binding --token tests/fixtures/timestamp/token_mock_bundle.json --target-hash sha256:1111111111111111111111111111111111111111111111111111111111111111
```

Expected at this point: valid mock/local timestamp artifacts; `trusted_time_claimed=false`; no
trusted timestamp proof.

## Attestation Stub Validation

```bash
klein-attestation validate-profile tests/fixtures/attestation/profile_mock_none.json
klein-attestation validate-statement tests/fixtures/attestation/statement_mock_backend.json
klein-attestation verify-binding --statement tests/fixtures/attestation/statement_mock_backend.json --backend-id opendrop_ewod_dry_run
```

Expected at this point: valid none/mock attestation artifacts; `hardware_attestation_claimed=false`;
no hardware attestation proof.

## V1 Conformance

```bash
klein-conform --suite tests/vectors/v1 --check-suite-integrity
klein-conform --suite tests/vectors/v1 --backend full_simulator --json
```

Expected at this point: `53 total`, `53 passed`, `0 failed`.

## V1 Negative Conformance

```bash
klein-conform --suite tests/vectors/v1 --category negative --backend full_simulator --json
```

Expected at this point: `32 total`, `32 passed`, `0 failed`.

## Golden Freshness

```bash
klein-regen-v1-goldens --suite tests/vectors/v1 --backend full_simulator --check
```

This must pass without changing existing HAIL goldens for docs-only passes.

## Legacy Report-Only Behavior

```bash
klein-conform --suite tests/vectors --legacy --backend full_simulator --json
```

Expected at this point: `120 total`, `2 passed`, `118 failed`, exit code `1`. This is expected
because the legacy corpus is migration material, not authoritative v1 conformance.

## Adapter And Archive Checks

```bash
klein-conformance-levels validate-catalog
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
```

Expected at this point:

- conformance catalog: `39 levels`, including `KCP-Core-Timestamp-Profile-Stub-v1` and
  `KCP-Core-Attestation-Profile-Stub-v1`;
- OpenDrop config validates as dry-run skeleton only;
- recorded run validates with `hardware_claimed: false`.

## Rust Verifier Validation

```bash
cargo --version
cargo test --manifest-path verifiers/rust/Cargo.toml
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

Expected at this point:

- Rust fixture CLI: `106 fixtures passed, 0 failed`;
- bundle verifier: `pass trusted_key_ids=klein-test-backend-001`.

## Build And Twine

```bash
python -m build
twine check dist/*
```

Both the wheel and sdist should pass `twine check`.

## Clean Export

```bash
klein-export-clean-repo --output klein-conformance-clean.zip --dry-run
```

Use this tool for handoff archives instead of zipping the working directory. It excludes local
artifacts such as `.git`, `.venv`, build output, cache directories, and Cargo `target`.

## Git Whitespace

```bash
git diff --check
git status --short
```

`git diff --check` should pass. `git status --short` may show unrelated work in this active alpha
branch; review it before publishing or committing.

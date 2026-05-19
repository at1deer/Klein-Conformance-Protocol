# Changelog

All notable changes to this project are documented here.

## [Unreleased]

### Public-alpha mirror patch (post `1.0.0a0`)

- Anchored the setuptools `MANIFEST` entry in `.gitignore` to `/MANIFEST`. The unanchored
  rule (boilerplate from the Python `.gitignore` template) was matching every `manifest/`
  directory on case-insensitive filesystems (Windows/macOS), so the public mirror was
  shipping without the per-vector signed-manifest fixtures or the directory-format Run
  Bundle manifest fixture.
- Restored signed-manifest vector fixtures that were missing from the public mirror:
  `manifest/run_manifest_signed.json` and `manifest/trust_policy.json` for the v1 vectors
  `012_hard_signed_run_manifest`, `N020_signed_manifest_tampered_payload`,
  `N021_signed_manifest_untrusted_key`, and `N022_signed_manifest_wrong_hail_digest`.
  Without these files, `klein-conform --check-suite-integrity` reported 8 issues and
  `klein-conform --suite tests/vectors/v1 --backend full_simulator --json` reported 49/53;
  N020/N021/N022 also failed for missing-file reasons instead of their intended tamper /
  untrusted-key / wrong-HAIL-digest semantics. Suite integrity now passes and v1 returns
  53/53 with N020/N021/N022 failing for their declared expected error codes.
- Restored `tests/fixtures/run_bundle/valid_signed_run_dir/manifest/run_manifest.json` so
  the bundled directory-format Run Bundle fixture is complete.
- Rewrote stale declared `sha256` references that were CRLF-poisoned during fixture
  generation on Windows (the prior fixture-author's working tree had `core.autocrlf=true`,
  so the declared hashes were computed against CRLF working-tree bytes while the committed
  blob is LF). Fixed declarations:
  - `raw_device_logs[0].sha256` in
    `tests/fixtures/recorded_run/dmf_dry_run_recorded_run/recorded_run.json`,
    `tests/fixtures/recorded_run/mock_recorded_run/recorded_run.json`, and
    `tests/fixtures/recorded_run/opendrop_dry_run_recorded_run/recorded_run.json`;
  - `hashes.run_manifest` and `hashes.trust_policy` in
    `tests/fixtures/run_bundle/valid_signed_run_dir/bundle.json`.
  Without this fix, `klein-recorded-run validate` fails on Linux fresh clones with
  `RAW_DEVICE_LOG_HASH_MISMATCH`, and `test_run_bundle_verify_zip_and_directory_match_result_schema`
  fails with `RUN_BUNDLE_MISSING_ENTRY`. A previous iteration of this patch mistakenly
  reported these declarations as correct; the Windows `autocrlf=true` smudge was masking
  the mismatch in the working tree only. A repo-wide audit of declared sha256 references
  against on-disk bytes now reports 0 stale declarations (excluding the intentionally
  wrong `9999…9999` HAIL digest in `N022`, which is the negative fixture's whole point).
- Re-normalized affected text fixtures to LF on disk so working-tree byte-level checks
  match the committed blob bytes on every platform.
- Documented the Rust verifier's required toolchain: the committed `Cargo.lock` is
  lockfile v4 and several dependencies require `edition2024`. Validated with `cargo 1.95.0`;
  the Ubuntu 24.04 distro-packaged `cargo 1.75` is too old. Updated `verifiers/rust/README.md`,
  `docs/VALIDATION_MATRIX.md`, `README.md`, `examples/public-alpha/DEMO_COMMANDS.md`, and
  `examples/public-alpha/EXPECTED_OUTPUTS.md` to call this out.

No HAIL goldens, vector intent, or claim boundaries changed in this patch.

### Other

- Added canonical hash utilities shared by HAIL, simulator evidence hashes, artifact hashing, and report binding.
- Added `klein-hash-artifact` for `.klein`, `.kleinc`, HAIL JSONL, and raw-byte hash checks.
- Bound v1 conformance report details to input artifact hashes, raw input hashes, profile/backend identifiers, and full-simulator DMF substrate fingerprints.
- Added HAIL `RUN_START` / `RUN_END` lifecycle events for execution vectors, including event-level artifact/profile/backend/substrate binding and pre-close digest evidence.
- Added v1 vector `010_hard_run_lifecycle_binding` to prove lifecycle binding in authoritative conformance.
- Added terminal `klein.hail.chain.v1` hash-chain digests in `RUN_END`, CLI chain verification, cross-language chain fixtures, and v1 vector `011_hard_hail_chain_binding`.
- Added Run Manifest v1 Ed25519 signing, schema, CLI create/verify/inspect tooling, public test-key fixtures, signature tamper tests, and optional conformance report verification fields.
- Added Trust Policy v1 schema/model, scoped backend/profile key authorization, CLI trust-policy verification, signed-conformance report fields, and v1 vector `012_hard_signed_run_manifest`.
- Added `KCP-Core-Signed-Conformance-v1`, the `klein-verify-run` reference verifier, signed-conformance result schema, shared conformance verifier integration, and negative signed-conformance vectors `N020`-`N022`.
- Added KCP Run Bundle v1, `.kcprun` bundle creation/verification, bundle result schema, strict zip security checks, vector `013_hard_run_bundle_signed_conformance`, and negative bundle vectors `N023`-`N025`.
- Added Independent Verifier v1, `klein-verify-bundle`, independent verifier result schema, cross-language fixture index, and import-boundary tests proving bundle verification does not use simulator/vector/conformance-runner state.
- Added cross-language canonicalization fixture targets with expected bytes and SHA-256 digests.
- Added the first non-Python independent verifier slice in Rust, covering cross-language Canonical JSON/JCS, HAIL Chain v1, Run Manifest signature, Trust Policy, and `.kcprun` bundle fixtures.
- Hardened the Rust verifier with Independent Verifier result JSON, Python/Rust semantic parity tests, stable negative `.kcprun` fixtures, bundle security parity tests, additional JCS edge coverage, and Trust Policy edge tests.
- Added Backend Identity Registry v1, registry-aware Trust Policy verification, registry-backed run bundle fixtures, Independent Verifier identity result fields, and Rust registry fixture support.
- Added signed Backend Identity Registry provenance, local registry authority trust roots, backend key lifecycle enforcement, signed-registry bundle fixtures, and Rust signed-registry verification.
- Added Backend Capability Declaration v1, signed backend capability fixtures, `klein-backend-capabilities`, bundle capability verification, and Rust capability fixture/bundle support.
- Added KCP Conformance Levels Matrix v1 with a canonical machine-readable catalog, `klein-conformance-levels`, capability-level enforcement, verifier reporting, and Rust fixture checks.
- Hardened DMF/EWOD Profile v1 alpha with a substantive profile spec, DMF capability/payload/frame schemas, shared DMF capability validation, targeted fixtures, a delta_tiles v1 vector, and Rust DMF capability fixture checks.
- Expanded DMF/EWOD v1 conformance coverage with unsorted multi-tick channel-list, sparse coordinate, malformed channel-list, and sparse coordinate OOB vectors plus DMF schema parity and cross-language payload fixtures.
- Added `.klein` Project v1 and `.kleinc` Container v1 specs/schemas, a central artifact validation API, `klein-artifact`, artifact schema/hash parity fixtures, v1 artifact positive/negative vectors, bundle artifact-schema reporting, and Rust artifact hash fixtures.
- Added Runbook v1 and Execution Trace v1 specs/schemas, Python builders/validators/comparison, `klein-runbook`, `klein-trace`, execution fixtures, v1 vector `021`, and Rust runbook/trace fixture checks.
- Added ECRP Retry/Replan Contract v1 with schema-backed policies, Python validators, `klein-ecrp`, ECRP fixtures, conformance result details, v1 vector `022`, conformance-level catalog entries, and Rust ECRP fixture checks.
- Added one simulator-only DMF transient-fault recovery success path using policy-approved `NUDGE_PULSE` retry evidence, recovery fixtures, v1 vector `023`, conformance report recovery fields, and Rust recovery fixture checks.
- Added Observation v1 simulator-backed DMF snapshots with schemas, Python validators, `klein-observation`, fixtures, v1 vector `024`, conformance report observation fields, and Rust observation fixture checks.
- Added HIL Readiness v1 as an interface/spec layer with contract/status schemas, Python validators, a mock HIL backend, `klein-hil`, HIL fixtures, Backend Capability Declaration HIL claim checks, conformance-level catalog entry, and Rust HIL fixture checks.
- Added Recorded Device Run v1 as an archive format with raw device log schema, Python validators, `klein-recorded-run`, mock recorded-run package fixtures, conformance-level catalog entries, and Rust recorded-run/raw-log fixture checks.
- Added Generic DMF Backend Adapter v1 as a dry-run skeleton with config/status schemas, Python adapter module, `klein-dmf-backend`, dry-run trace/raw-log/observation generation, adapter-produced recorded-run fixtures, conformance-level catalog entries, and Rust adapter config/status fixture checks.
- Added OpenDrop/EWOD Adapter Skeleton v1 as a dry-run/config-only boundary with config/status/command-intent schemas, row-major electrode mapping, `klein-opendrop-backend`, dry-run OpenDrop intent/raw-log/observation generation, adapter-produced recorded-run fixtures, conformance-level catalog entries, and Rust OpenDrop fixture checks.
- Added OpenDrop Transport Planning v1 as a disabled experimental transport boundary with config and serial-command schemas, deterministic command-stream serialization, `klein-opendrop-backend validate-transport` / `serialize-runbook`, strict current-alpha hardware IO and endpoint rejection, cross-language fixtures, and GPL/vendor-boundary documentation.
- Tightened OpenDrop current-alpha schemas so hardware IO, active endpoints/baud rates, connected device status, and hardware-allowed serial commands fail schema validation as well as runtime validation.
- Reworked public-alpha documentation with a reader-facing README, architecture map, current-alpha claims page, quickstart, validation matrix, bundle verification guide, DMF profile overview, adapter guide, roadmap, release checklist, and specs/docs indexes.
- Added `docs/WHITEPAPER.md` as the public-alpha whitepaper synthesis for the current evidence, conformance, verifier, DMF/EWOD, adapter, and non-claim boundaries.
- Added Trusted Timestamp Profile v1 stub with schemas, mock/local profile and token fixtures, `klein-timestamp`, canonical token/profile hashing, target-hash binding checks, conformance-level catalog entry, and Rust fixture parity without claiming trusted timestamp proof.
- Added Attestation Profile v1 stub with schemas, none/mock profile and statement fixtures, `klein-attestation`, canonical statement/profile hashing, subject/backend binding checks, conformance-level catalog entry, and Rust fixture parity without claiming hardware attestation proof.

## [1.0.0a0] - 2026-05-14

### Added

- Repositioned Klein as a substrate conformance protocol for physical execution under uncertainty.
- Introduced the authoritative Klein Core v1 vector suite under `tests/vectors/v1`.
- Added strict HAIL v1 validation, canonical JSONL helpers, generated-golden checks, and schema parity tests.
- Added executable `.klein`, `.kleinc`, HAIL JSONL, DMF/EWOD payload, and negative evidence vectors.
- Added DMF/EWOD profile modules with capability/topology-driven payload validation.
- Added negative evidence assertions for failures that must prove emitted HAIL evidence, not only error codes.
- Added clean export tooling for handoff archives that exclude ignored local artifacts.
- Added JSON conformance report schema/documentation and v1 suite integrity checks.

### Changed

- Split the conformance harness into smaller modules for suite loading, vector contracts, backends, comparison, reporting, and CLI behavior.
- Restored Klein Canonical JSONL v1 as RFC 8785/JCS per-event canonicalization with HAIL event ordering.
- Made legacy vectors explicit report-only migration material instead of authoritative v1 conformance.
- Updated CI to require compile checks, unit tests, v1 conformance, v1 negative conformance, golden freshness, suite integrity, and Ruff on the cleaned v1 surface.

### Not Included

- No physical hardware certification.
- No full autonomous recovery in the reference simulator.
- No field-level numeric ENVELOPE tolerances yet.
- The legacy 120-vector corpus is not authoritative Klein Core v1 conformance.

## [1.0.0-alpha] - 2026-01-07

January prototype baseline. This material is retained as historical context; split Klein Core v1 specs and the `1.0.0a0` package alpha supersede it for current conformance claims.

### Added

- Initial `.klein` and `.kleinc` artifact models.
- Early HAIL event log, simulator, substrate API, conformance harness, and 120-vector experimental corpus.
- Early protocol master spec, examples, and CI.

### Superseded

- Legacy terminology such as SCI, DSB, RSB, and LCP is superseded in strict v1 by HAIL, SImgB, RImgB, and ECRP.
- The January 120-vector corpus remains migration material and is not authoritative Klein Core v1 conformance.

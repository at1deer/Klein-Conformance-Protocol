# Klein Claims Ledger

Klein uses this ledger to preserve the original ambition without overstating the current alpha.

Layers:

- `CURRENT_ALPHA`: implemented and tested in this repository today.
- `TARGET_V1`: required before Klein Core v1 and the v1 whitepaper claims are fully true.
- `LONG_HORIZON`: broader substrate-neutral / programmable-matter goals.

## CURRENT_ALPHA

### CA-001

- `claim_text`: Klein has an authoritative v1 vector suite.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented
- `repo_evidence`: `tests/vectors/v1/index.json`, `klein-conform --suite tests/vectors/v1`
- `missing_work`: continue deliberate migration from the legacy corpus
- `blocking_tests_or_artifacts`: v1 suite integrity check
- `relevant_specs`: `specs/core/conformance-report-v1.md`
- `relevant_vector_categories`: v1 core, hail, dmf, negative

### CA-002

- `claim_text`: HAIL v1 events are strictly validated.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented
- `repo_evidence`: `src/klein/hail/validation.py`, `tests/test_hail_core.py`, `tests/test_schema_parity.py`
- `missing_work`: broader cross-language validators
- `blocking_tests_or_artifacts`: HAIL schema parity tests
- `relevant_specs`: `specs/core/hail-v1.md`
- `relevant_vector_categories`: hail, negative

### CA-003

- `claim_text`: v1 conformance uses real declared inputs.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented
- `repo_evidence`: v1 vector `vector.json` contracts and `VECTOR_INPUT_MISSING` behavior
- `missing_work`: independent non-simulator backend fixtures
- `blocking_tests_or_artifacts`: suite integrity tests and v1 conformance runs
- `relevant_specs`: `specs/core/conformance-levels-v1.md`
- `relevant_vector_categories`: core, dmf, hail

### CA-004

- `claim_text`: Negative vectors require expected failure codes.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented
- `repo_evidence`: `src/klein/conformance/comparison.py`, `tests/test_conformance_harness.py`
- `missing_work`: expand negative coverage as profiles mature
- `blocking_tests_or_artifacts`: negative conformance run
- `relevant_specs`: `specs/core/error-codes-v1.md`
- `relevant_vector_categories`: negative

### CA-005

- `claim_text`: Negative evidence assertions can prove specific HAIL evidence.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented
- `repo_evidence`: N014 ECRP bounded failure vector
- `missing_work`: richer temporal/order assertions
- `blocking_tests_or_artifacts`: evidence assertion pass/fail tests
- `relevant_specs`: `specs/core/conformance-report-v1.md`
- `relevant_vector_categories`: negative, ECRP

### CA-006

- `claim_text`: DMF/EWOD alpha payload validation is capability/topology-driven.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented
- `repo_evidence`: `src/klein/profiles/dmf/`
- `missing_work`: independent hardware backend profile fixtures
- `blocking_tests_or_artifacts`: DMF positive and negative v1 vectors
- `relevant_specs`: `specs/profiles/dmf/`
- `relevant_vector_categories`: dmf, negative

### CA-007

- `claim_text`: ECRP currently emits bounded failure evidence, while hardware recovery remains future work.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented as bounded evidence only
- `repo_evidence`: N014 and execution engine ECRP attempt emission
- `missing_work`: retry/replan policy, sensing comparison, success classification
- `blocking_tests_or_artifacts`: ECRP bounded evidence vector
- `relevant_specs`: `specs/core/error-codes-v1.md`
- `relevant_vector_categories`: negative, ECRP

### CA-008

- `claim_text`: The legacy suite is report-only.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented
- `repo_evidence`: legacy conformance summary marks `legacy_namespace: true`, `authoritative_v1: false`
- `missing_work`: batch migration plan execution
- `blocking_tests_or_artifacts`: legacy report schema tests
- `relevant_specs`: `docs/LEGACY_MIGRATION_PLAN.md`
- `relevant_vector_categories`: legacy

### CA-009

- `claim_text`: V1 conformance reports bind output evidence to declared input artifact hashes and, for the full simulator, DMF profile/substrate fingerprints.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented and tested for alpha v1 reports
- `repo_evidence`: conformance report details, `src/klein/common/hashing.py`, `src/klein/profiles/dmf/fingerprints.py`, `tests/test_hash_binding.py`
- `missing_work`: independent verifier checks and stronger signed-conformance profile coverage
- `blocking_tests_or_artifacts`: report schema tests and hash-binding tests
- `relevant_specs`: `specs/core/conformance-report-v1.md`, `specs/core/hail-digest-chain-v1.md`
- `relevant_vector_categories`: all v1, dmf

### CA-010

- `claim_text`: V1 execution HAIL streams bind the run to the declared input artifact, profile, backend, mode, and simulator substrate fingerprint via lifecycle events.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for full-simulator execution vectors
- `repo_evidence`: HAIL `RUN_START` / `RUN_END` models, vector `010_hard_run_lifecycle_binding`, lifecycle report fields, `tests/test_hash_binding.py`
- `missing_work`: backend identity registry, hardware attestation, independent verifier coverage
- `blocking_tests_or_artifacts`: lifecycle vector, pre-close digest tests, report consistency tests
- `relevant_specs`: `specs/core/hail-v1.md`, `specs/core/hail-digest-chain-v1.md`, `specs/core/conformance-report-v1.md`
- `relevant_vector_categories`: core, dmf, negative execution

### CA-011

- `claim_text`: V1 execution HAIL streams are tamper-evident through a terminal pre-close HAIL chain digest.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for full-simulator execution vectors
- `repo_evidence`: `src/klein/hail/chain.py`, `klein-hail-canon --verify-chain`, vector `011_hard_hail_chain_binding`, `tests/test_hail_chain.py`, `tests/fixtures/hail_chain/`
- `missing_work`: backend identity registry, hardware attestation, independent non-Python verifier
- `blocking_tests_or_artifacts`: chain tamper tests, chain fixture tests, chain CLI tests
- `relevant_specs`: `specs/core/hail-digest-chain-v1.md`, `specs/core/hail-v1.md`
- `relevant_vector_categories`: core, verifier, future security

### CA-012

- `claim_text`: Lifecycle-bound HAIL can be externally signed with Run Manifest v1.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for alpha fixtures and CLI tooling
- `repo_evidence`: `src/klein/crypto/`, `src/klein/tools/run_manifest.py`, `schemas/run_manifest.schema.json`, `tests/test_run_manifest.py`, `tests/fixtures/run_manifest/`
- `missing_work`: backend identity registry if policy-only scoping is insufficient; independent verifier implementations
- `blocking_tests_or_artifacts`: Run Manifest signature/tamper/trust tests and CLI create/verify tests
- `relevant_specs`: `specs/core/run-manifest-v1.md`, `specs/core/trust-policy-v1.md`, `specs/core/hail-digest-chain-v1.md`
- `relevant_vector_categories`: verifier, signed-conformance

### CA-013

- `claim_text`: Trust Policy v1 can authorize signed run manifests for specific backend/profile scopes.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for alpha signed-conformance vectors and CLI verification
- `repo_evidence`: `src/klein/crypto/trust.py`, `schemas/trust_policy.schema.json`, vector `012_hard_signed_run_manifest`, `tests/fixtures/crypto/trust_policy_test.json`, `tests/test_run_manifest.py`
- `missing_work`: formal backend identity registry, key rotation policy, independent verifier implementations
- `blocking_tests_or_artifacts`: trust-policy schema tests, scope mismatch/revocation tests, signed-conformance vector
- `relevant_specs`: `specs/core/trust-policy-v1.md`, `specs/core/run-manifest-v1.md`
- `relevant_vector_categories`: signed-conformance, verifier

### CA-014

- `claim_text`: KCP-Core-Signed-Conformance-v1 is defined and mechanically enforced by a reference verifier.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for alpha signed-conformance fixtures and v1 vectors
- `repo_evidence`: `specs/core/signed-conformance-v1.md`, `src/klein/verifier/`, `src/klein/tools/verify_run.py`, `schemas/signed_conformance_result.schema.json`, vector `012_hard_signed_run_manifest`, negative vectors `N020`-`N022`, `tests/test_signed_conformance.py`
- `missing_work`: independent non-Python verifier, backend identity registry, trusted timestamp/attestation profiles
- `blocking_tests_or_artifacts`: signed-conformance verifier tests, v1 positive and negative conformance runs, verifier JSON schema tests
- `relevant_specs`: `specs/core/signed-conformance-v1.md`, `specs/core/signed-conformance-report-v1.md`, `specs/core/run-manifest-v1.md`, `specs/core/trust-policy-v1.md`
- `relevant_vector_categories`: signed-conformance, negative, verifier

### CA-015

- `claim_text`: KCP Run Bundle v1 packages signed run evidence into a portable verifiable artifact.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for alpha fixtures, CLI tooling, and v1 bundle vectors
- `repo_evidence`: `specs/core/run-bundle-v1.md`, `src/klein/bundle/`, `src/klein/tools/run_bundle.py`, `schemas/run_bundle.schema.json`, `schemas/run_bundle_result.schema.json`, vector `013_hard_run_bundle_signed_conformance`, negative vectors `N023`-`N025`, `tests/test_run_bundle.py`
- `missing_work`: independent `.kcprun` verifier, registry/timestamp/attestation profiles, production packaging compatibility policy
- `blocking_tests_or_artifacts`: bundle fixture tests, bundle CLI tests, bundle vector positive/negative conformance
- `relevant_specs`: `specs/core/run-bundle-v1.md`, `specs/core/run-bundle-result-v1.md`, `specs/core/signed-conformance-v1.md`
- `relevant_vector_categories`: run-bundle, signed-conformance, negative, verifier

### CA-016

- `claim_text`: KCP has a Python reference independent verifier for `.kcprun` bundles.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for bundle-only verification without simulator/vector/conformance-runner state
- `repo_evidence`: `specs/core/independent-verifier-v1.md`, `schemas/independent_verifier_result.schema.json`, `src/klein/verifier/independent.py`, `src/klein/tools/verify_bundle.py`, `tests/fixtures/cross_language/fixtures.json`, `tests/test_independent_verifier.py`
- `missing_work`: backend identity registry, trusted timestamps, hardware/substrate attestation, physical evidence threat model
- `blocking_tests_or_artifacts`: independent verifier schema tests, CLI tests, cross-language fixture index, import-boundary tests
- `relevant_specs`: `specs/core/independent-verifier-v1.md`, `specs/core/independent-verifier-result-v1.md`, `specs/core/run-bundle-v1.md`
- `relevant_vector_categories`: verifier, run-bundle, signed-conformance

### CA-017

- `claim_text`: KCP has a first non-Python independent verifier slice.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented in Rust for cross-language fixtures, positive/negative `.kcprun` bundle verification, schema-valid verifier JSON, and core Python/Rust semantic parity
- `repo_evidence`: `verifiers/rust/`, `verifiers/README.md`, `tests/test_rust_verifier.py`, `tests/test_rust_python_verifier_parity.py`, `tests/fixtures/cross_language/fixtures.json`
- `missing_work`: full `klein.independent_verifier_result.v1` parity across all optional paths, additional language implementations, registry/timestamp/attestation profiles
- `blocking_tests_or_artifacts`: Rust fixture tests, Rust/Python parity tests, Python wrapper tests for Cargo availability, cross-language fixture index
- `relevant_specs`: `specs/core/independent-verifier-v1.md`, `specs/core/run-bundle-v1.md`, `specs/core/hail-digest-chain-v1.md`
- `relevant_vector_categories`: verifier, run-bundle, signed-conformance

### CA-018

- `claim_text`: KCP has Backend Identity Registry v1 for declaring backend identities and published signing keys.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for local/test registries, Python registry-aware trust verification, registry-backed bundles, and Rust registry fixtures
- `repo_evidence`: `specs/core/backend-identity-registry-v1.md`, `schemas/backend_identity_registry.schema.json`, `src/klein/crypto/registry.py`, `tests/fixtures/crypto/backend_registry_test.json`, `tests/test_backend_identity_registry.py`, `tests/test_registry_trust_policy.py`, `tests/fixtures/run_bundle/valid_signed_run_with_registry.kcprun`
- `missing_work`: registry provenance/signing, key rotation/delegation, multiple registry roots, timestamp/attestation profiles
- `blocking_tests_or_artifacts`: registry schema tests, registry-backed trust tests, registry-backed bundle fixture, cross-language registry fixtures
- `relevant_specs`: `specs/core/backend-identity-registry-v1.md`, `specs/core/trust-policy-v1.md`, `specs/core/run-bundle-v1.md`
- `relevant_vector_categories`: verifier, run-bundle, signed-conformance

### CA-019

- `claim_text`: KCP backend registries can carry signed local provenance and enforce backend key lifecycle status.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for Ed25519-signed registry envelopes, local Trust Policy registry authorities, active/revoked/retired validity-window behavior, Python verifier paths, and Rust signed-registry fixtures/bundles
- `repo_evidence`: `src/klein/crypto/registry.py`, `src/klein/tools/backend_registry.py`, `tests/fixtures/crypto/backend_registry_signed_test.json`, `tests/fixtures/crypto/trust_policy_registry_authority_test.json`, `tests/fixtures/run_bundle/valid_signed_run_with_signed_registry.kcprun`, `tests/test_signed_backend_registry.py`, `verifiers/rust/`
- `missing_work`: delegation chains, registry transparency logs, multiple registry roots policy, trusted timestamps, hardware attestation
- `blocking_tests_or_artifacts`: signed registry tests, registry authority trust tests, cross-language signed registry fixtures, signed-registry bundle verification
- `relevant_specs`: `specs/core/backend-identity-registry-v1.md`, `specs/core/trust-policy-v1.md`, `specs/core/independent-verifier-v1.md`
- `relevant_vector_categories`: verifier, run-bundle

### CA-020

- `claim_text`: KCP has signed backend capability declarations for backend/profile/run-scope capability claims.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for signed Backend Capability Declaration v1, Python signature/registry/trust/scope verification, bundle-carried capabilities, and Rust capability fixtures/bundles
- `repo_evidence`: `specs/core/backend-capability-declaration-v1.md`, `schemas/backend_capability_declaration.schema.json`, `src/klein/crypto/capabilities.py`, `src/klein/tools/backend_capabilities.py`, `tests/fixtures/capabilities/`, `tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun`, `tests/test_backend_capabilities.py`, `verifiers/rust/`
- `missing_work`: Run Manifest/RUN_START capability hash binding, mature profile capability schemas, hardware attestation, trusted timestamps, physical observation
- `blocking_tests_or_artifacts`: capability declaration tests, cross-language capability fixtures, capability bundle verification
- `relevant_specs`: `specs/core/backend-capability-declaration-v1.md`, `specs/core/run-bundle-v1.md`, `specs/core/independent-verifier-v1.md`
- `relevant_vector_categories`: verifier, run-bundle, profiles

### CA-021

- `claim_text`: KCP has a machine-readable Conformance Levels Matrix v1 that controls supported backend capability claims.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for canonical catalog validation, Python capability enforcement, independent verifier reporting, CLI inspection, and Rust fixture/bundle checks
- `repo_evidence`: `specs/core/conformance-levels-v1.md`, `specs/core/conformance-levels-matrix-v1.md`, `specs/catalogs/conformance_levels.v1.json`, `schemas/conformance_levels.schema.json`, `src/klein/conformance/levels.py`, `src/klein/tools/conformance_levels.py`, `tests/test_conformance_levels.py`
- `missing_work`: published badges, profile-specific level schemas, manifest/RUN_START capability hash binding, HIL support, hardware attestation, trusted timestamps
- `blocking_tests_or_artifacts`: conformance level catalog tests, capability declaration enforcement tests, cross-language level fixtures
- `relevant_specs`: `specs/core/conformance-levels-v1.md`, `specs/core/conformance-levels-matrix-v1.md`
- `relevant_vector_categories`: verifier, run-bundle, profiles

### CA-022

- `claim_text`: DMF/EWOD Profile v1 alpha is specified, schema-backed, and conformance-tested for current simulator behavior.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for profile spec, DMF capability/payload/frame schemas, shared Python validation, backend capability enforcement, fixtures, and targeted v1 DMF vector coverage
- `repo_evidence`: `specs/profiles/dmf/dmf-ewod-v1.md`, `schemas/profiles/dmf/`, `src/klein/profiles/dmf/`, `tests/test_dmf_profile.py`, `tests/test_dmf_schema_parity.py`, `tests/fixtures/profiles/dmf/`, `tests/vectors/v1/dmf/014_frame_sequence_delta_tiles`, `tests/vectors/v1/dmf/015_channel_list_multi_tick_unsorted`, `tests/vectors/v1/dmf/016_frame_sequence_sparse_coordinates`, `tests/vectors/v1/negative/N026_channel_list_missing_voltage`, `tests/vectors/v1/negative/N027_sparse_coordinate_out_of_grid`
- `missing_work`: observation semantics, profile-specific independent validators, simulated closed-loop recovery, HIL levels, trusted timestamps, hardware attestation
- `blocking_tests_or_artifacts`: DMF schema/runtime validation tests, v1 DMF vectors, Rust DMF capability fixture checks
- `relevant_specs`: `specs/profiles/dmf/dmf-ewod-v1.md`, `specs/core/conformance-levels-v1.md`
- `relevant_vector_categories`: profiles, dmf

### CA-023

- `claim_text`: `.klein` Project v1 and `.kleinc` Container v1 artifacts are schema-backed, centrally validated, and canonically hashed for current alpha conformance.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for Project/Container specs, JSON schemas, Python artifact validation API, `klein-artifact` CLI, schema parity tests, v1 positive/negative artifact vectors, bundle artifact-schema reporting, and Rust artifact hash fixtures
- `repo_evidence`: `specs/artifacts/klein-project-v1.md`, `specs/artifacts/klein-container-v1.md`, `schemas/klein_project.schema.json`, `schemas/klein_container.schema.json`, `src/klein/artifacts/`, `src/klein/tools/artifact.py`, `tests/test_artifact_schema_parity.py`, `tests/fixtures/artifacts/`, `tests/vectors/v1/core/019_project_artifact_schema_valid`, `tests/vectors/v1/core/020_container_artifact_schema_valid`, `tests/vectors/v1/negative/N028_project_missing_profile`, `tests/vectors/v1/negative/N029_container_missing_payload`, `tests/vectors/v1/negative/N030_artifact_unsupported_schema_version`, `tests/vectors/v1/negative/N031_artifact_profile_payload_mismatch`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: runbook/trace separation, richer artifact provenance, manifest/RUN_START `backend_capabilities_hash`, observation semantics, HIL levels, trusted timestamps, hardware attestation
- `blocking_tests_or_artifacts`: artifact schema parity tests, artifact hash tests, v1 artifact vectors, bundle result schema tests, Rust cross-language artifact fixtures
- `relevant_specs`: `specs/artifacts/klein-project-v1.md`, `specs/artifacts/klein-container-v1.md`, `specs/core/error-codes-v1.md`
- `relevant_vector_categories`: core, negative, run-bundle

### CA-024

- `claim_text`: KCP has explicit Runbook v1 and Execution Trace v1 artifacts separating planned execution from actual issued/applied execution path.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for schema-backed runbook/trace artifacts, Python builders/validators/comparison, simulator report details, CLIs, fixtures, v1 vector `021`, and Rust cross-language fixture checks
- `repo_evidence`: `specs/core/runbook-v1.md`, `specs/core/execution-trace-v1.md`, `schemas/runbook.schema.json`, `schemas/execution_trace.schema.json`, `src/klein/execution/`, `src/klein/tools/runbook.py`, `src/klein/tools/trace.py`, `tests/test_execution_artifacts.py`, `tests/fixtures/execution/`, `tests/vectors/v1/core/021_runbook_trace_generated_for_container`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: RUN_START/RUN_END binding to runbook/trace hashes, optional bundle entries, formal ECRP retry/replan, simulated closed-loop recovery, observation semantics, HIL readiness, trusted timestamps, hardware attestation
- `blocking_tests_or_artifacts`: runbook/trace schema tests, trace/runbook comparison tests, v1 vector `021`, cross-language runbook/trace fixtures
- `relevant_specs`: `specs/core/runbook-v1.md`, `specs/core/execution-trace-v1.md`, `specs/core/error-codes-v1.md`
- `relevant_vector_categories`: core, execution, verifier

### CA-025

- `claim_text`: ECRP Retry/Replan Contract v1 defines and enforces policy-bound bounded failure evidence.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for schema-backed ECRP policies, HAIL attempt-sequence validation, trace/runbook recovery-evidence validation, CLI validation, conformance result details, fixtures, v1 vector `022`, and Rust cross-language fixture checks
- `repo_evidence`: `specs/core/ecrp-v1.md`, `schemas/ecrp_policy.schema.json`, `src/klein/execution/ecrp.py`, `src/klein/tools/ecrp.py`, `tests/test_ecrp_contract.py`, `tests/fixtures/ecrp/`, `tests/vectors/v1/core/022_ecrp_bounded_failure_contract`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: successful simulated closed-loop recovery, observation semantics, HIL readiness, trusted timestamps, hardware attestation, physical recovery proof
- `blocking_tests_or_artifacts`: ECRP policy tests, ECRP HAIL/trace fixture tests, v1 vector `022`, Rust cross-language ECRP fixtures
- `relevant_specs`: `specs/core/ecrp-v1.md`, `specs/core/hail-v1.md`, `specs/core/runbook-v1.md`, `specs/core/execution-trace-v1.md`, `specs/core/error-codes-v1.md`
- `relevant_vector_categories`: core, ECRP, execution, verifier

### CA-026

- `claim_text`: One simulator-only DMF transient fault recovery path succeeds when policy, HAIL, and trace evidence all support it.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for deterministic transient DMF channel/frame failure recovered by policy-approved `NUDGE_PULSE` retry in the full simulator
- `repo_evidence`: `src/klein/sim/execution_engine.py`, `src/klein/execution/ecrp.py`, `src/klein/execution/trace.py`, `tests/test_ecrp_contract.py`, `tests/fixtures/ecrp/policy_simulated_recovery_success.json`, `tests/fixtures/ecrp/hail_simulated_recovery_success.jsonl`, `tests/fixtures/ecrp/trace_simulated_recovery_success.json`, `tests/vectors/v1/core/023_ecrp_simulated_recovery_success`
- `missing_work`: broader replan around permanent faults, observation semantics, HIL readiness, trusted timestamps, hardware attestation, physical recovery proof
- `blocking_tests_or_artifacts`: vector `023`, recovery ECRP fixtures, Rust recovery fixtures
- `relevant_specs`: `specs/core/ecrp-v1.md`, `specs/core/execution-trace-v1.md`, `specs/profiles/dmf/dmf-ewod-v1.md`
- `relevant_vector_categories`: core, ECRP, DMF, execution

### CA-027

- `claim_text`: Observation v1 exists for simulator-backed DMF observation snapshots aligned with trace/runbook evidence.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for simulator source snapshots, policy validation, trace/runbook alignment, conformance details, CLI validation, fixtures, v1 vector `024`, and Rust cross-language fixture checks
- `repo_evidence`: `specs/core/observation-v1.md`, `schemas/observation_snapshot.schema.json`, `schemas/observation_policy.schema.json`, `src/klein/execution/observation.py`, `src/klein/tools/observation.py`, `tests/test_observation_semantics.py`, `tests/fixtures/observation/`, `tests/vectors/v1/core/024_dmf_simulated_observation_snapshot`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: HAIL/RUN_START/manifest observation hash binding, optional bundle observation entries, hardware sensor source semantics, HIL readiness, trusted timestamps, hardware attestation, physical observation proof
- `blocking_tests_or_artifacts`: observation schema tests, CLI tests, vector `024`, Rust observation fixtures
- `relevant_specs`: `specs/core/observation-v1.md`, `specs/profiles/dmf/dmf-ewod-v1.md`, `specs/core/execution-trace-v1.md`
- `relevant_vector_categories`: core, observation, DMF, verifier

### CA-028

- `claim_text`: HIL Readiness v1 exists as an interface/spec layer for future hardware backends.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for contract/status schemas, Python validation, a mock interface backend, CLI checks, Backend Capability Declaration validation, conformance-level catalog entry, fixtures, and Rust cross-language fixture checks
- `repo_evidence`: `specs/core/hil-readiness-v1.md`, `schemas/hil_backend_contract.schema.json`, `schemas/hil_backend_status.schema.json`, `src/klein/hil/`, `src/klein/tools/hil.py`, `tests/test_hil_readiness.py`, `tests/fixtures/hil/`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: recorded hardware run format, real HIL adapter skeletons, hardware observation source semantics, trusted timestamps, hardware attestation, and physical proof threat model
- `blocking_tests_or_artifacts`: HIL fixture tests, `klein-hil` validation, cross-language HIL fixtures
- `relevant_specs`: `specs/core/hil-readiness-v1.md`, `specs/core/backend-capability-declaration-v1.md`, `specs/core/conformance-levels-v1.md`
- `relevant_vector_categories`: verifier, hardware-readiness

### CA-029

- `claim_text`: Recorded Device Run v1 exists as an archive format for simulator/mock device-side run records.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for recorded-run schemas, raw-device-log validation, Python package validation, `klein-recorded-run`, mock recorded-run package fixtures, conformance-level catalog entries, and Rust cross-language fixture checks
- `repo_evidence`: `specs/core/recorded-device-run-v1.md`, `schemas/recorded_device_run.schema.json`, `schemas/raw_device_log.schema.json`, `src/klein/recording/`, `src/klein/tools/recorded_run.py`, `tests/test_recorded_run.py`, `tests/fixtures/recorded_run/`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: real backend adapter skeletons, hardware source support, hardware sensor semantics, trusted timestamps, hardware attestation, media evidence policy, and physical proof threat model
- `blocking_tests_or_artifacts`: recorded-run tests, `klein-recorded-run` validation, raw log fixtures, Rust recorded-run/raw-log fixtures
- `relevant_specs`: `specs/core/recorded-device-run-v1.md`, `specs/core/run-bundle-v1.md`, `specs/core/hil-readiness-v1.md`, `specs/core/observation-v1.md`
- `relevant_vector_categories`: verifier, hardware-readiness, archive

### CA-030

- `claim_text`: Generic DMF Backend Adapter v1 exists as a dry-run skeleton for future DMF/EWOD backends.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for config/status schemas, Python dry-run adapter, runbook-to-command translation skeleton, trace/raw-log/mock-observation generation, mock recorded-run package generation, CLI tooling, fixtures, conformance-level catalog entries, and Rust config/status fixture checks
- `repo_evidence`: `specs/profiles/dmf/dmf-backend-adapter-v1.md`, `schemas/profiles/dmf/dmf_backend_adapter_config.schema.json`, `schemas/profiles/dmf/dmf_backend_adapter_status.schema.json`, `src/klein/backends/dmf/`, `src/klein/tools/dmf_backend.py`, `tests/test_dmf_backend_adapter.py`, `tests/fixtures/backends/dmf/`, `tests/fixtures/recorded_run/dmf_dry_run_recorded_run/`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: OpenDrop/EWOD adapter skeleton, real HIL backend, hardware source support, hardware sensor semantics, trusted timestamps, hardware attestation, and physical proof threat model
- `blocking_tests_or_artifacts`: DMF adapter fixture tests, `klein-dmf-backend` dry-run checks, adapter-generated recorded-run validation, Rust adapter fixtures
- `relevant_specs`: `specs/profiles/dmf/dmf-backend-adapter-v1.md`, `specs/core/hil-readiness-v1.md`, `specs/core/recorded-device-run-v1.md`, `specs/profiles/dmf/dmf-ewod-v1.md`
- `relevant_vector_categories`: profile, backend-adapter, archive

### CA-031

- `claim_text`: OpenDrop/EWOD Adapter Skeleton v1 exists as a dry-run/config-only backend boundary.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for config/status/command-intent schemas, row-major electrode mapping, Python dry-run intent generation, trace/raw-log/mock-observation output, mock recorded-run package generation, CLI tooling, fixtures, conformance-level catalog entries, and Rust config/intent fixture checks
- `repo_evidence`: `specs/profiles/dmf/opendrop-ewod-adapter-v1.md`, `schemas/profiles/dmf/opendrop_adapter_config.schema.json`, `schemas/profiles/dmf/opendrop_adapter_status.schema.json`, `schemas/profiles/dmf/opendrop_command_intent.schema.json`, `src/klein/backends/dmf/opendrop/`, `src/klein/tools/opendrop_backend.py`, `tests/test_opendrop_backend_adapter.py`, `tests/fixtures/backends/dmf/opendrop/`, `tests/fixtures/recorded_run/opendrop_dry_run_recorded_run/`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: real OpenDrop transport, signed OpenDrop backend identity/capability declaration, HIL execution, hardware source support, hardware sensor semantics, trusted timestamps, hardware attestation, and physical proof threat model
- `blocking_tests_or_artifacts`: OpenDrop adapter fixture tests, `klein-opendrop-backend` dry-run checks, OpenDrop adapter-generated recorded-run validation, Rust OpenDrop fixtures
- `relevant_specs`: `specs/profiles/dmf/opendrop-ewod-adapter-v1.md`, `specs/profiles/dmf/dmf-backend-adapter-v1.md`, `specs/core/hil-readiness-v1.md`, `specs/core/recorded-device-run-v1.md`
- `relevant_vector_categories`: profile, backend-adapter, archive

### CA-032

- `claim_text`: OpenDrop Transport Planning v1 exists as a disabled transport config and deterministic command-stream boundary.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for transport config schema, serial-command schema, Python validation/serialization, CLI validation/serialization, fixtures, conformance-level catalog entries, and Rust shape fixture checks
- `repo_evidence`: `specs/profiles/dmf/opendrop-transport-planning-v1.md`, `schemas/profiles/dmf/opendrop_transport_config.schema.json`, `schemas/profiles/dmf/opendrop_serial_command.schema.json`, `src/klein/backends/dmf/opendrop/transport.py`, `src/klein/backends/dmf/opendrop/serialization.py`, `src/klein/tools/opendrop_backend.py`, `tests/test_opendrop_backend_adapter.py`, `tests/fixtures/backends/dmf/opendrop/`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: real OpenDrop serial transport, hardware access gate implementation, device handshake, hardware source semantics, sensor semantics, trusted timestamp authority validation, real attestation verification, and physical proof threat model
- `blocking_tests_or_artifacts`: transport fixtures, `klein-opendrop-backend validate-transport`, `klein-opendrop-backend serialize-runbook`, Rust transport fixture checks
- `relevant_specs`: `specs/profiles/dmf/opendrop-transport-planning-v1.md`, `specs/profiles/dmf/opendrop-ewod-adapter-v1.md`
- `non_claims`: OpenDrop hardware support, HIL execution, physical truth, sensor proof, hardware attestation, trusted timestamp proof, copied/vendored OpenDrop firmware or controller code

### CA-032

- `claim_text`: Trusted Timestamp Profile v1 stub exists for mock/local timestamp evidence boundaries.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for profile/token schemas, Python validation, canonical hashing, target-hash binding checks, CLI tooling, fixtures, conformance-level catalog entry, and Rust cross-language fixture checks
- `repo_evidence`: `specs/core/trusted-timestamp-profile-v1.md`, `schemas/timestamp_profile.schema.json`, `schemas/timestamp_token.schema.json`, `src/klein/timestamping/`, `src/klein/tools/timestamp.py`, `tests/test_timestamp_profile.py`, `tests/fixtures/timestamp/`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: external timestamp authority validation, RFC 3161 or equivalent profile, timestamp trust roots, verifier trust-policy integration, optional bundle/recorded-run inclusion, hardware attestation integration
- `blocking_tests_or_artifacts`: timestamp fixture tests, `klein-timestamp` validation/binding checks, Rust timestamp fixtures
- `relevant_specs`: `specs/core/trusted-timestamp-profile-v1.md`, `specs/core/conformance-levels-v1.md`, `specs/core/error-codes-v1.md`
- `relevant_vector_categories`: verifier, timestamp-stub

### CA-033

- `claim_text`: Attestation Profile v1 stub exists for none/mock attestation evidence boundaries.
- `layer`: `CURRENT_ALPHA`
- `status`: implemented for profile/statement schemas, Python validation, canonical hashing, subject/backend binding checks, CLI tooling, fixtures, conformance-level catalog entry, and Rust cross-language fixture checks
- `repo_evidence`: `specs/core/attestation-profile-v1.md`, `schemas/attestation_profile.schema.json`, `schemas/attestation_statement.schema.json`, `src/klein/attestation/`, `src/klein/tools/attestation.py`, `tests/test_attestation_profile.py`, `tests/fixtures/attestation/`, `tests/fixtures/cross_language/fixtures.json`, `verifiers/rust/`
- `missing_work`: TPM/TEE/quote validation, hardware trust roots, verifier trust-policy/backend-registry integration, optional bundle/recorded-run inclusion, trusted timestamp integration, physical evidence threat model
- `blocking_tests_or_artifacts`: attestation fixture tests, `klein-attestation` validation/binding checks, Rust attestation fixtures
- `relevant_specs`: `specs/core/attestation-profile-v1.md`, `specs/core/conformance-levels-v1.md`, `specs/core/error-codes-v1.md`
- `relevant_vector_categories`: verifier, attestation-stub

## TARGET_V1

### TV1-001

- `claim_text`: Klein Canonical JSONL v1 uses RFC 8785/JCS canonical JSON per HAIL event.
- `layer`: `TARGET_V1`
- `status`: implemented in Python alpha and exercised by the Rust verifier for the cross-language canonicalization fixtures
- `repo_evidence`: `src/klein/hail/canonical.py`, `src/klein/common/hashing.py`, `tests/test_jcs_canonicalization.py`, `tests/fixtures/canonicalization/cross_language/`, `verifiers/rust/`
- `missing_work`: additional independent verifier implementations and broader language coverage
- `blocking_tests_or_artifacts`: independent verifier must pass the cross-language fixture suite
- `relevant_specs`: `specs/algorithms/klein_canon.jsonl.v1.md`
- `relevant_vector_categories`: hail, canonicalization

### TV1-002

- `claim_text`: HAIL digests are stable cross-language verifier inputs.
- `layer`: `TARGET_V1`
- `status`: partially implemented; execution streams now include lifecycle binding, pre-close digest evidence, terminal hash-chain digests, signed Run Manifest v1 fixtures, Trust Policy v1 authorization, Backend Identity Registry v1 declarations, a Python reference signed-conformance verifier, portable KCP Run Bundle v1 packages, a Python reference independent verifier contract, and a first Rust verifier slice
- `repo_evidence`: `klein-hail-canon`, `klein-hash-artifact`, `klein-run-manifest`, `klein-verify-run`, `klein-run-bundle`, `klein-verify-bundle`, `verifiers/rust/`, digest fields in conformance details, `RUN_START` / `RUN_END`, cross-language canonical fixtures, chain fixtures, run manifest fixtures, trust policy fixtures, backend registry fixtures, signed-conformance fixtures, run-bundle fixtures, cross-language fixture index
- `missing_work`: full independent verifier result parity across languages, registry provenance/signing, key rotation/delegation, and formal trust root decisions
- `blocking_tests_or_artifacts`: verifier CLI tests, cross-language fixtures, signed-conformance vectors, run-bundle vectors
- `relevant_specs`: `specs/core/hail-digest-chain-v1.md`, `specs/core/run-manifest-v1.md`, `specs/core/trust-policy-v1.md`, `specs/core/signed-conformance-v1.md`, `specs/core/run-bundle-v1.md`, `specs/core/independent-verifier-v1.md`
- `relevant_vector_categories`: hail

### TV1-003

- `claim_text`: Conformance reports are schema-stable.
- `layer`: `TARGET_V1`
- `status`: implemented for alpha JSON shape, including input/profile/substrate binding fields
- `repo_evidence`: `schemas/conformance_report.schema.json`, report schema tests, v1 conformance JSON output
- `missing_work`: versioned report schema compatibility policy
- `blocking_tests_or_artifacts`: report schema validation tests
- `relevant_specs`: `specs/core/conformance-report-v1.md`
- `relevant_vector_categories`: all v1 and legacy report-only

### TV1-004

- `claim_text`: DMF/EWOD profile conformance is sufficient for independent backend implementation.
- `layer`: `TARGET_V1`
- `status`: partial
- `repo_evidence`: DMF validation vectors and profile modules
- `missing_work`: independent backend fixture contract and driver conformance suite
- `blocking_tests_or_artifacts`: DMF backend fixture tests
- `relevant_specs`: `specs/profiles/dmf/`
- `relevant_vector_categories`: dmf, capability

### TV1-005

- `claim_text`: ECRP has a formal bounded retry/replan contract.
- `layer`: `TARGET_V1`
- `status`: partial bounded evidence only
- `repo_evidence`: N014 and ECRP error codes
- `missing_work`: checkpoint selection, retry policy, replan bounds, observation comparison
- `blocking_tests_or_artifacts`: ECRP retry/replan conformance vectors
- `relevant_specs`: `specs/core/error-codes-v1.md`
- `relevant_vector_categories`: ECRP, negative, future recovery

### TV1-006

- `claim_text`: Substrate profiles can be independently implemented against Klein Core.
- `layer`: `TARGET_V1`
- `status`: partial
- `repo_evidence`: profile/core split, substrate API boundary, simulator capability/topology fingerprints in reports
- `missing_work`: profile capability negotiation tests and backend certification vectors
- `blocking_tests_or_artifacts`: independent profile backend test harness
- `relevant_specs`: `specs/profiles/`, `specs/core/`
- `relevant_vector_categories`: profile, capability

## LONG_HORIZON

### LH-001

- `claim_text`: Klein becomes a TCP/IP-style conformance layer for programmable matter.
- `layer`: `LONG_HORIZON`
- `status`: architectural target
- `repo_evidence`: Core/Profile split and v1 conformance foundation
- `missing_work`: multiple independent profiles, hardware-backed implementations, stable verifier ecosystem
- `blocking_tests_or_artifacts`: multi-profile conformance suite
- `relevant_specs`: split v1 specs and future profile specs
- `relevant_vector_categories`: future multi-substrate

### LH-002

- `claim_text`: Klein enables substrate-neutral execution across heterogeneous physical media.
- `layer`: `LONG_HORIZON`
- `status`: architectural target
- `repo_evidence`: substrate-neutral core artifacts and first DMF profile
- `missing_work`: at least two non-DMF profiles and demonstrated profile isolation
- `blocking_tests_or_artifacts`: cross-profile conformance vectors
- `relevant_specs`: `specs/profiles/`
- `relevant_vector_categories`: future profile suites

### LH-003

- `claim_text`: Klein supports cryptographic proof/evidence chains for execution logs.
- `layer`: `LONG_HORIZON`
- `status`: roadmap
- `repo_evidence`: canonical HAIL JSONL digests, artifact hashes, simulator substrate fingerprints, verifier CLIs, `RUN_START` / `RUN_END` lifecycle binding, terminal HAIL chain digests, alpha signed run manifests, Trust Policy v1, Trusted Timestamp Profile v1 stub, Attestation Profile v1 stub
- `missing_work`: external trusted timestamp authority validation, real hardware attestation verification, physical threat model
- `blocking_tests_or_artifacts`: signed digest-chain verifier tests
- `relevant_specs`: `specs/core/hail-digest-chain-v1.md`, `specs/core/run-manifest-v1.md`, `specs/core/trust-policy-v1.md`
- `relevant_vector_categories`: future verifier/security

### LH-004

- `claim_text`: Klein supports independent hardware-backed implementations.
- `layer`: `LONG_HORIZON`
- `status`: roadmap
- `repo_evidence`: substrate driver boundary and clean conformance report shape
- `missing_work`: hardware driver conformance harness, safety gates, real observation ingestion
- `blocking_tests_or_artifacts`: hardware-in-loop report-only then required profile vectors
- `relevant_specs`: substrate backend boundary specs
- `relevant_vector_categories`: future hardware-in-loop

### LH-005

- `claim_text`: Klein recovery actually repairs or replans under sensed substrate divergence.
- `layer`: `LONG_HORIZON`
- `status`: roadmap
- `repo_evidence`: bounded ECRP evidence vector
- `missing_work`: sensing model, alternate geodesic route calculation, retry/replan policies, replay evidence
- `blocking_tests_or_artifacts`: closed-loop recovery vectors with deterministic fault injection
- `relevant_specs`: ECRP and profile recovery specs
- `relevant_vector_categories`: future recovery

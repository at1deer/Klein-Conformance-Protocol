# TARGET_V1 Test Plan

This plan maps target claims to the tests and artifacts needed before the stronger v1 and
whitepaper claims are fully defensible.

## Canonicalization

- Add RFC 8785 / JCS fixture tests for objects, arrays, strings, Unicode, integers, floats,
  exponent forms, and rejected non-finite values.
- Maintain cross-language canonicalization fixtures with expected bytes and SHA-256 digests.
- Require independent implementations to match `klein.canon.jsonl.v1` fixture bytes.

## HAIL Digest Verification

- Verify `klein-hail-canon` against valid HAIL JSONL, invalid HAIL JSONL, expected canonical
  bytes, and expected digests.
- Verify `klein-hash-artifact` against `.klein`, `.kleinc`, HAIL JSONL, and malformed inputs.
- Bind conformance report digests to artifact hashes, profile identifiers, backend identifiers, and
  simulator substrate fingerprints.
- Verify execution-vector `RUN_START` fields match report-level artifact/profile/backend/substrate
  binding fields.
- Verify `RUN_END.preclose_hail_digest` matches the canonical digest over every event before
  `RUN_END`.
- Verify `RUN_END.preclose_hail_chain_digest` matches `klein.hail.chain.v1` over every pre-close
  event.
- Verify insertion, deletion, reordering, and field tampering are detected by chain tests or
  canonical-order checks.
- Add negative digest mismatch vectors.
- Keep cross-language HAIL chain fixtures current as the chain algorithm evolves.

## Conformance Reports

- Validate v1, v1-negative, and legacy report-only JSON output against
  `schemas/conformance_report.schema.json`.
- Assert input artifact hash, raw input hash, profile/backend fields, and substrate fingerprint
  fields are present where applicable.
- Add report schema version compatibility tests before changing the JSON shape.

## Portable Artifacts

- Validate `.klein` Project v1 and `.kleinc` Container v1 artifacts against
  `schemas/klein_project.schema.json` and `schemas/klein_container.schema.json`.
- Require runtime artifact validators to agree with schema validators for representative valid,
  missing-profile, missing-payload, unsupported-version, and malformed-payload examples.
- Verify `klein-artifact validate`, `klein-artifact inspect`, and `klein-artifact hash` on
  project/container artifacts.
- Maintain artifact canonical hash fixtures proving key ordering and whitespace do not change
  `klein.canon.json.v1` digests while semantic payload changes do.
- Keep v1 artifact positive/negative vectors current without making legacy vectors authoritative.

## Runbook And Execution Trace

- Validate Runbook v1 and Execution Trace v1 artifacts against `schemas/runbook.schema.json` and
  `schemas/execution_trace.schema.json`.
- Verify trace/runbook comparison detects missing steps, tick/operation mismatches, invalid status
  combinations, and explicit failed steps.
- Keep `klein-runbook` and `klein-trace` CLI checks in the final validation matrix.
- Keep HAIL as the canonical evidence log; runbook/trace artifacts are planning/execution records,
  not physical proof.
- Defer mandatory bundle inclusion and RUN_START/RUN_END hash binding until the runbook/trace
  contract is hardened.

## DMF/EWOD Independent Backend

- Define backend fixture inputs and expected HAIL evidence independent of the reference simulator.
- Run the same DMF payload vectors against at least one non-reference backend adapter.
- Add capability negotiation tests for topology, voltage/frequency ranges, addressing mode, and
  unsupported payload formats.

## ECRP Retry/Replan

- Validate ECRP Policy v1 against `schemas/ecrp_policy.schema.json` and the Python/Rust fixture
  checks.
- Reject unknown strategies, attempts beyond `max_attempts`, missing terminal failure evidence,
  unplanned HARD-mode replan, and success claims unsupported by policy.
- Require trace/runbook recovery evidence when policy declares `requires_trace_evidence`.
- Keep vector `023_ecrp_simulated_recovery_success` as the first simulator-only recovery-success
  proof: transient DMF failure, `NUDGE_PULSE` attempt, failed original trace step, successful retry,
  and `RUN_END SUCCESS`.
- Add deterministic fault-injection vectors for retry count, checkpoint selection, alternate route
  selection, observation comparison, and final success/failure classification.
- Require HAIL evidence for every retry/replan attempt.
- Keep bounded failure evidence as the implemented minimum behavior until real recovery exists.

## Profile Capability Negotiation

- Test that profile validators consume declared capabilities/topology rather than hardcoded board
  assumptions.

## Observation Semantics

- Validate Observation v1 policies and simulator snapshots against `schemas/observation_policy.schema.json`
  and `schemas/observation_snapshot.schema.json`.
- Keep vector `024_dmf_simulated_observation_snapshot` as the first simulator-backed DMF observation
  proof.
- Require observation/trace alignment for simulated observation claims.
- Keep hardware sensor sources, HIL observation, trusted timestamps, attestation, and physical truth
  as target/future work until explicit machinery exists.
- Add negative vectors for capability mismatch, missing topology, and unsupported primitives.

## HIL Readiness

- Validate HIL Backend Contract v1 and HIL Backend Status v1 against
  `schemas/hil_backend_contract.schema.json` and `schemas/hil_backend_status.schema.json`.
- Keep `klein-hil` contract/status/mock checks in the final validation matrix.
- Treat `KCP-Core-HIL-Readiness-v1` as interface readiness only: mock/dry-run operation shape,
  explicit health, explicit emergency stop/reset semantics, and declared observation source type.
- Require Backend Capability Declaration HIL claims to include a HIL contract hash and reject
  hardware execution, HIL-L1, or hardware attestation claims in current alpha.
- Keep recorded hardware run format, real hardware adapters, HIL-L0/L1 observed conformance,
  trusted timestamps, and physical proof as target/future work.
- Do not add execution vectors that imply real hardware support until hardware source semantics and
  safety gates are explicit.

## Recorded Device Runs

- Validate Recorded Device Run v1 archive indexes against `schemas/recorded_device_run.schema.json`.
- Validate Raw Device Log v1 JSONL events against `schemas/raw_device_log.schema.json`.
- Keep `klein-recorded-run validate`, `inspect`, `hash`, `validate-raw-log`, and `create-mock` in
  the validation matrix.
- Treat recorded-run packages as a wrapper above `.kcprun`, not a replacement for signed run bundles.
- Reject `source_type: hardware`, `hardware_claimed: true`, attestation metadata, and trusted
  timestamp metadata in strict current-alpha mode.
- Keep real HIL hardware recorded runs, media evidence policy, hardware sensor source semantics,
  trusted timestamps, and attested hardware evidence as target/future work.

## Trusted Timestamp Profile

- Validate Trusted Timestamp Profile v1 stub artifacts against
  `schemas/timestamp_profile.schema.json` and `schemas/timestamp_token.schema.json`.
- Keep `klein-timestamp validate-profile`, `validate-token`, `hash-profile`, `hash-token`,
  `verify-binding`, `inspect-token`, and `create-mock` in the validation matrix.
- Require current-alpha timestamp profiles and tokens to use `mock_local`, `trusted_time_claimed:
  false`, no trust roots, no signatures, and no external timestamp authority.
- Report timestamp status using `not_present`, `not_evaluated`, `mock`, `invalid`, and
  `trusted_future`; do not report trusted proof for mock/local tokens.
- Keep RFC 3161 or equivalent token validation, TSA trust roots, bundle/recorded-run timestamp token
  inclusion, and trust-policy integration as TARGET_V1 work.
- Keep timestamp proof combined with hardware attestation and physical evidence under an explicit
  threat model as LONG_HORIZON work.

## Attestation Profile

- Validate Attestation Profile v1 stub artifacts against `schemas/attestation_profile.schema.json`
  and `schemas/attestation_statement.schema.json`.
- Keep `klein-attestation validate-profile`, `validate-statement`, `hash-profile`,
  `hash-statement`, `verify-binding`, `inspect-statement`, `create-mock`, and `create-none` in the
  validation matrix.
- Require current-alpha attestation profiles and statements to use `mock_none` / `none` / `mock`,
  `hardware_attestation_claimed: false`, no hardware roots, no quotes, no measurements, no
  signatures, and no external hardware root.
- Report attestation status using `not_present`, `not_evaluated`, `none`, `mock`, `invalid`, and
  `attested_future`; do not report hardware attestation proof for none/mock statements.
- Keep TPM/TEE/quote verification, hardware trust roots, bundle/recorded-run attestation statement
  inclusion, and trust-policy/backend-registry integration as TARGET_V1 work.
- Keep hardware attestation combined with trusted timestamps and physical evidence under an explicit
  threat model as LONG_HORIZON work.

## Generic DMF Backend Adapter

- Validate Generic DMF Backend Adapter v1 config/status artifacts against
  `schemas/profiles/dmf/dmf_backend_adapter_config.schema.json` and
  `schemas/profiles/dmf/dmf_backend_adapter_status.schema.json`.
- Keep `klein-dmf-backend validate-config`, `inspect-config`, `dry-run-runbook`, and
  `create-mock-recording` in the validation matrix.
- Require current-alpha adapter configs to use `dry_run` or `mock` mode, `hardware_io_enabled:
  false`, `safety.require_estop: true`, and profile `dmf/v1`.
- Validate dry-run adapter outputs: Execution Trace v1, Raw Device Log v1, simulator/mock
  Observation v1 snapshots, and Recorded Device Run v1 packages.
- Keep adapter config outside `.kcprun` and Run Manifest v1 for now; future packages may include
  `backend/adapter_config.json`.
- Keep OpenDrop/EWOD protocol details, real hardware IO, hardware sensor semantics, trusted
  timestamps, and hardware attestation as target/future work.

## OpenDrop/EWOD Adapter

- Validate OpenDrop/EWOD Adapter Skeleton v1 config/status/command-intent artifacts against
  `schemas/profiles/dmf/opendrop_adapter_config.schema.json`,
  `schemas/profiles/dmf/opendrop_adapter_status.schema.json`, and
  `schemas/profiles/dmf/opendrop_command_intent.schema.json`.
- Keep `klein-opendrop-backend validate-config`, `map-electrodes`, `dry-run-runbook`, and
  `create-mock-recording` in the validation matrix.
- Require current-alpha OpenDrop configs to use `dry_run` or `mock` mode, `hardware_io_enabled:
  false`, `transport.transport_kind: none`, `safety.require_estop: true`, and profile `dmf/v1`.
- Validate row-major and explicit electrode mapping, including duplicate and out-of-range failures.
- Validate dry-run OpenDrop command intents, raw log operations, mock observations, and Recorded
  Device Run v1 packages without claiming device IO.
- Keep signed OpenDrop backend identity/capability declaration, real transport, HIL execution,
  hardware sensor semantics, trusted timestamps, hardware attestation, and physical proof as
  target/future work.

## Signature and Hash-Chain Future Work

- Consume HAIL chain fixtures from at least one independent non-Python verifier.
- Keep signed Run Manifest v1 fixtures current and validate them against
  `schemas/run_manifest.schema.json`.
- Keep Trust Policy v1 fixtures current and validate them against
  `schemas/trust_policy.schema.json`.
- Validate `klein-verify-run --json` output against
  `schemas/signed_conformance_result.schema.json`.
- Verify Ed25519 signatures bind to HAIL digest, terminal chain digest, `RUN_START`
  artifact/profile/backend fields, `RUN_END` status fields, and substrate fingerprints.
- Test payload tampering, signature tampering, wrong public keys, malformed base64, and wrong HAIL
  digest references.
- Maintain signed-conformance vectors where valid signatures and trusted backend/profile policy
  authorization are required.
- Require `KCP-Core-Signed-Conformance-v1` reference checks to pass for positive vectors and fail
  with canonical error codes for negative signed-conformance vectors.
- Keep KCP Run Bundle v1 fixtures current for directory and `.kcprun` forms.
- Validate `klein-run-bundle verify --json` output against
  `schemas/run_bundle_result.schema.json`.
- Test bundle integrity failures for missing entries, raw hash mismatch, unsupported format, and
  malicious zip member paths.
- Require independent verifiers to consume `.kcprun` bundles as the portable exchange unit.
- Require the Rust verifier slice to pass the cross-language fixture index and valid/negative
  `.kcprun` bundle checks in Cargo tests.
- Validate Rust `verify-bundle --json` against `schemas/independent_verifier_result.schema.json`
  and compare core bindings/checks against the Python independent verifier.
- Require future non-Python verifiers to match `klein.independent_verifier_result.v1` exactly for
  the cross-language fixture index.
- Keep `tests/fixtures/cross_language/fixtures.json` as the implementation-neutral fixture index
  for canonical bytes, artifact hashes, runbook/trace hashes and comparison, HAIL chain, signed
  manifest, trust policy, Backend Identity Registry v1, signed-conformance, timestamp profile/token
  stubs, attestation profile/statement stubs, and `.kcprun` verification.
- Expand Backend Identity Registry v1 toward signed registry provenance, key rotation, delegation,
  and multiple trust roots.
- Exercise signed registry provenance fixtures across Python and Rust, including invalid signatures,
  untrusted authorities, revoked keys, and signed-registry `.kcprun` bundles.
- Exercise Backend Capability Declaration v1 fixtures across Python and Rust, including invalid
  signatures, unsupported profile/mode scope, substrate mismatch, and invalid DMF capability ranges.
- Add future Run Manifest/RUN_START binding to `backend_capabilities_hash` once the bundle-level
  contract is stable.
- Treat `specs/catalogs/conformance_levels.v1.json` as the source of truth for backend capability
  claims. Add profile-specific matrices for DMF/EWOD before publishing conformance badges.
- Expand DMF/EWOD from alpha simulator validation into observation semantics, formal recovery
  evidence, and HIL readiness without claiming hardware proof before attestation/measurement
  profiles exist.
- Keep expanding authoritative v1 DMF vectors in small batches. Current alpha coverage includes
  channel-list, sparse, bitmap, delta_tiles, and explicit rle rejection; observation and recovery
  vectors remain target work.
- Extend current simulator substrate fingerprint tests to signed or attested backends.
- Add third-party verifier tests that do not import the reference Python implementation beyond the
  existing Rust wrapper that only invokes Cargo as an external process.

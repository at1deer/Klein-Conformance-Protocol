# Conformance Report v1

`klein-conform --json` emits a machine-readable conformance report with a stable top-level
shape:

- `summary`: aggregate run metadata and counts
- `results`: one object per executed vector

`summary.authoritative_v1` is true only when the run contains strict v1 vectors, is not a
legacy run, and uses the authoritative `full_simulator` backend. `summary.legacy_namespace` is
true for report-only legacy runs, mixed/non-v1 material, or non-authoritative harness backends.
Legacy failures are migration evidence, not Klein Core v1 failure.

Each result records:

- `vector_id`
- `vector_name`
- `outcome`
- `message`
- `expected_result`
- `actual_result`
- `expected_error_code`
- `actual_error_code`
- `validation_stage`
- `reason`
- `duration_ms`
- `classification`
- `details`

Evidence assertion failures include assertion diagnostics in `details`, including the failed
assertion index and assertion object when available.

For strict v1 vectors, `details` also binds the observed evidence to the declared input and
execution context:

- `input_raw_sha256`: SHA-256 over the declared input file bytes when the file exists.
- `input_artifact_hash`: canonical artifact hash when the input can be parsed and
  canonicalized.
- `input_artifact_hash_mode`: `canonical_json` for `.klein`/`.kleinc` JSON artifacts or
  `canonical_hail_jsonl` for HAIL JSONL inputs.
- `input_artifact_canonicalization`: `klein.canon.json.v1` or `klein.canon.jsonl.v1`.
- `profile_id` and `profile_version`: the declared vector profile binding.
- `backend_id` and `backend_version`: the backend that produced the evidence.
- `substrate_capabilities_hash`, `substrate_topology_hash`, and `substrate_fingerprint`:
  simulator profile/substrate declaration fingerprints when the backend executes against a
  declared substrate context.
- `run_start_present`, `run_end_present`, and `lifecycle_bound`: whether the HAIL stream carries
  lifecycle binding evidence and whether the reported pre-close digest matches.
- `run_start_artifact_hash`, `run_start_profile_id`, `run_start_backend_id`, and
  `run_start_substrate_fingerprint`: selected RUN_START fields copied into the report for
  consistency checks.
- `preclose_hail_digest`, `preclose_hail_digest_computed`, `preclose_hail_digest_matches`, and
  `event_count_preclose`: RUN_END digest closure diagnostics.
- `hail_chain_algorithm`, `preclose_hail_chain_digest`,
  `run_end_preclose_hail_chain_digest`, `hail_chain_matches_run_end`,
  `event_count_chained`, and `hail_chain_canonical_order_ok`: terminal HAIL chain diagnostics for
  lifecycle-bound execution streams.
- `signed_conformance`, `run_manifest_present`, `run_manifest_verified`,
  `run_manifest_signature_status`, `run_manifest_trust_status`, `run_manifest_key_id`,
  `run_manifest_signature_algorithm`, and `run_manifest_error_code`: Run Manifest v1 and Trust
  Policy v1 verification diagnostics when a vector declares `run_manifest_path`.
- `ecrp_policy_present`, `ecrp_policy_hash`, `ecrp_contract_status`, `ecrp_attempt_count`,
  `ecrp_terminal_failure_status`, and `ecrp_error_code`: ECRP Retry/Replan Contract v1
  diagnostics for vectors that emit recovery-attempt evidence.
- `ecrp_recovery_status`, `ecrp_recovery_strategy`, and `trace_recovery_validated`: simulator-only
  recovery-success diagnostics for vectors that prove policy-approved retry recovery.
- `observation_present`, `observation_count`, `observation_contract_status`,
  `observation_model`, `observation_source_type`, `observation_recovery_validated`, and
  `observation_error_code`: Observation v1 diagnostics for vectors that require simulator-backed
  observation evidence.

Malformed negative vectors may include `input_raw_sha256` while leaving
`input_artifact_hash` null. That is intentional: a raw byte digest is useful evidence, but Klein
does not claim a canonical artifact digest for an artifact that cannot be parsed.

Execution vectors should carry `RUN_START` / `RUN_END`. Direct HAIL validation vectors intentionally
preserve and validate their supplied stream as-is, so these lifecycle fields are false/null there.

The JSON Schema is published at `schemas/conformance_report.schema.json`.

Run Manifest v1 verification is optional unless a vector declares `signed_conformance: true`.
Signed-conformance vectors require a valid manifest signature, payload/HAIL binding, and Trust
Policy v1 authorization for the backend/profile scope. A trusted policy result still proves only
local authorization, not hardware attestation or physical truth.

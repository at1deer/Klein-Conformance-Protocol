# KCP Run Bundle Result v1

`klein.run_bundle_result.v1` is the stable JSON result emitted by `klein-run-bundle verify --json`.

The schema is `schemas/run_bundle_result.schema.json`.

## Fields

- `result_version`: `klein.run_bundle_result.v1`
- `overall_status`: `pass` or `fail`
- `bundle_path`
- `bundle_format`: `directory` or `zip`
- `checks`: bundle schema, bundle entry hash, and signed-conformance statuses
- `errors`: machine-readable failures
- `warnings`: non-fatal diagnostics
- `signed_conformance_result`: embedded `klein.signed_conformance_result.v1` output when bundle integrity permits verification
- `bundle_hashes`: raw entry hashes declared by `bundle.json`
- `resolved_paths`: local verifier paths for declared entries
- `hail_digest`
- `hail_chain_digest`
- `run_manifest_key_ids`
- `trust_status`
- `backend_id`
- `profile_id`
- `artifact_hash`
- `substrate_fingerprint`

Status values are `pass`, `fail`, `not_applicable`, and `not_evaluated`.

`overall_status=pass` means bundle integrity passed and the bundled evidence satisfied `KCP-Core-Signed-Conformance-v1` under the bundled Trust Policy v1. It does not mean hardware attestation, trusted timestamping, physical truth proof, or backend certification beyond local policy authorization.

# Signed Conformance Result v1

`klein.signed_conformance_result.v1` is the stable JSON result emitted by `klein-verify-run --json` and returned by the reference verifier.

The schema is `schemas/signed_conformance_result.schema.json`.

## Required Fields

- `result_version`: `klein.signed_conformance_result.v1`
- `overall_status`: `pass` or `fail`
- `checks`: per-check statuses for HAIL validation, canonicalization, lifecycle binding, chain verification, manifest schema, manifest payload binding, signature verification, trust authorization, artifact binding, and optional report binding
- `errors`: machine-readable failures with `check`, `error_code`, and `message`
- `warnings`: non-fatal diagnostics
- `hail_digest`
- `hail_chain_digest`
- `manifest_key_ids`
- `trusted_key_ids`
- `backend_id`
- `profile_id`
- `profile_version`
- `artifact_hash`
- `substrate_fingerprint`

Status values are `pass`, `fail`, `not_applicable`, and `not_evaluated`.

## Interpretation

`overall_status=pass` means the run satisfies `KCP-Core-Signed-Conformance-v1` under the supplied local Trust Policy v1. It does not mean hardware attestation, trusted timestamping, physical truth proof, or backend certification beyond local policy authorization.

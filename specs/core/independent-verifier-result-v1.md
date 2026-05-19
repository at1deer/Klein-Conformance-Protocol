# Independent Verifier Result v1

`klein.independent_verifier_result.v1` is the stable JSON result emitted by `klein-verify-bundle --json`.

The schema is `schemas/independent_verifier_result.schema.json`.

## Shape

- `result_version`: `klein.independent_verifier_result.v1`
- `overall_status`: `pass` or `fail`
- `bundle_format`: `zip` or `directory`
- `bundle_path`: verifier input path
- `checks`: ordered protocol checks for bundle, HAIL, manifest, trust policy, optional backend registry identity, and optional report agreement
- `bindings`: artifact/HAIL/backend/profile/substrate/key bindings extracted from verified evidence
- `errors`: machine-readable failures
- `warnings`: non-fatal diagnostics

Registry-aware results include `backend_identity_registry` and `backend_identity_resolution`
checks, plus identity binding fields such as `identity_status`, `backend_registry_id`,
`backend_registry_hash`, `registry_backend_id`, `registry_key_id`, `backend_key_status`,
`registry_signed`, `registry_signature_status`, `registry_provenance_status`,
`registry_authority_id`, and `key_lifecycle_status`.

Capability-aware bundle results include `backend_capabilities_present`,
`backend_capability_declaration_hash`, `backend_capability_signature_status`,
`backend_capability_trust_status`, `backend_capability_scope_status`, and
`backend_capability_error_code`. These fields are `not_evaluated` or `null` when a bundle does not
carry `identity/backend_capabilities.json`.

When backend capabilities are present, result bindings also include `declared_conformance_levels`,
`verified_conformance_levels`, `conformance_level_catalog_status`,
`conformance_level_dependency_status`, and `conformance_level_error_code`.

This result is intended as the cross-language comparison target for future Rust, TypeScript, and C++ verifiers.

`overall_status=pass` means the bundle is internally consistent and satisfies `KCP-Core-Signed-Conformance-v1` under its Trust Policy v1. It does not claim hardware attestation, trusted time, physical truth, or backend certification beyond local policy authorization.

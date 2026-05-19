# Trust Policy v1

Trust Policy v1 authorizes Ed25519 backend signing keys for scoped Klein Run Manifest v1
verification.

It answers a narrow question:

```text
Is this cryptographically valid manifest signature authorized for the backend/profile scope claimed
inside the signed payload?
```

It does not prove physical execution, hardware attestation, trusted time, or substrate truth.

## CURRENT_ALPHA

The alpha implements `klein.trust_policy.v1` as the executable backend identity mechanism.

Policy entries bind:

- `key_id`
- raw base64 Ed25519 public key
- signature algorithm
- allowed backend ids
- allowed profile ids and versions
- allowed manifest versions
- local status and optional validity fields

`klein-run-manifest verify --trust-policy policy.json` verifies signatures first, then evaluates
the policy. A valid signature can still fail with `trust_status=untrusted`.

`klein-verify-run` requires a Trust Policy v1 document. A valid signature with no policy may remain
acceptable for manifest-only inspection, but it is not signed-conformant.

## Policy Shape

```json
{
  "policy_version": "klein.trust_policy.v1",
  "policy_id": "klein-test-policy",
  "description": "Test policy for Klein signed-manifest fixtures.",
  "trusted_keys": [
    {
      "key_id": "klein-test-backend-001",
      "public_key_encoding": "base64.raw.ed25519",
      "public_key": "<base64>",
      "signature_algorithm": "Ed25519",
      "trust_scope": {
        "backend_ids": ["full_simulator"],
        "profile_ids": ["dmf"],
        "profile_versions": ["v1"],
        "manifest_versions": ["klein.run_manifest.v1"]
      },
      "status": "trusted",
      "not_before": null,
      "not_after": null,
      "notes": "Public test key. Not production."
    }
  ],
  "revoked_keys": []
}
```

The published JSON Schema is `schemas/trust_policy.schema.json`.

## Status Semantics

- `signature_status=valid`: Ed25519 verification succeeded over canonical manifest payload bytes.
- `signature_status=invalid`: cryptographic verification, signature encoding, or signature shape
  failed.
- `signature_status=missing`: the manifest contains no signatures.
- `trust_status=trusted`: at least one valid signature is authorized by the supplied policy.
- `trust_status=untrusted`: signature is valid, but the policy rejects the key or scope.
- `trust_status=not_evaluated`: no trust policy or explicit trust key check was supplied.
- `trust_status=indeterminate`: policy validity fields could not be evaluated, for example because
  `created_at` is absent while `not_before` or `not_after` is present.

## Backend Identity Registry Interaction

Trust Policy v1 can operate in two alpha modes:

- self-contained entries that include `public_key`
- registry-backed entries with `source = "registry"` that reference `key_id` and rely on Backend Identity Registry v1 for key material

When a Backend Identity Registry is supplied, the verifier first resolves the manifest
`backend_id` / `backend_version` / `profile_id` / `profile_version` / signature `key_id` against
the registry. Registry resolution is necessary but not sufficient for trust: policy scope still
decides authorization.

If a policy entry includes `public_key` and a registry is supplied, the public key must agree with
the registry key. If a policy entry omits `public_key`, `source = "registry"` is required and a
registry must be supplied.

Trust Policy v1 can also locally trust registry signing authorities:

```json
{
  "trusted_registry_authorities": [
    {
      "authority_id": "klein-test-registry-root",
      "signature_algorithm": "Ed25519",
      "public_key_encoding": "base64.raw.ed25519",
      "public_key": "<base64>",
      "registry_ids": ["klein-test-registry"],
      "status": "trusted",
      "not_before": null,
      "not_after": null,
      "notes": "Public test registry root. Not production."
    }
  ]
}
```

This is local provenance trust, not global PKI. It proves that the registry payload was signed by a
locally trusted registry authority; it does not prove hardware identity or physical execution.

## TARGET_V1

Before stronger signed-conformance claims are complete, Klein should add:

- registry transparency, delegation, key-rotation policy, and multiple trust roots
- independent verifier implementations for Run Manifest v1 and Trust Policy v1
- policy compatibility and revocation tests
- backend identity registry semantics for publication, rotation, delegation, and attestation roots

## LONG_HORIZON

Trust Policy v1 is necessary for backend identity binding but not sufficient for physical truth.
Trusted timestamps, hardware attestation, substrate attestation, and sensed recovery evidence remain
future work.

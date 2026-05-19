# Backend Identity Registry v1

Backend Identity Registry v1 declares backend identities and their published signing keys.

It is an identity declaration layer, not a trust decision layer. Trust Policy v1 remains the local authorization mechanism that decides which registered backend identities and keys are trusted for particular backend/profile/manifest scopes.

## Format

Backend Identity Registry v1 supports two alpha forms.

Unsigned direct form:

```json
{
  "registry_version": "klein.backend_identity_registry.v1",
  "registry_id": "klein-test-registry",
  "description": "Test registry for Klein backend identity fixtures.",
  "issued_at": null,
  "backends": [
    {
      "backend_id": "full_simulator",
      "backend_name": "Klein Full Simulator",
      "backend_vendor": "Klein Reference",
      "backend_versions": ["1.0.0a0"],
      "profiles": [
        {
          "profile_id": "dmf",
          "profile_versions": ["v1"]
        }
      ],
      "keys": [
        {
          "key_id": "klein-test-backend-001",
          "signature_algorithm": "Ed25519",
          "public_key_encoding": "base64.raw.ed25519",
          "public_key": "<base64>",
          "status": "active",
          "not_before": null,
          "not_after": null,
          "notes": "Public test key. Not production."
        }
      ],
      "metadata": {
        "test_fixture": true
      }
    }
  ]
}
```

Signed envelope form:

```json
{
  "registry_version": "klein.backend_identity_registry.v1",
  "payload": {
    "registry_id": "klein-test-registry",
    "description": "Test registry for Klein backend identity fixtures.",
    "issued_at": null,
    "backends": []
  },
  "signatures": [
    {
      "signature_algorithm": "Ed25519",
      "authority_id": "klein-test-registry-root",
      "public_key_encoding": "base64.raw.ed25519",
      "public_key": "<base64>",
      "signature_encoding": "base64.raw.ed25519",
      "signature": "<base64>"
    }
  ]
}
```

The JSON Schema is `schemas/backend_identity_registry.schema.json`.

Signed registry signatures are computed over RFC 8785/JCS canonical bytes of `registry["payload"]`.
The raw JSON text and `signatures` array are never signed.

## Semantics

- A registry declares backend identity metadata and key material.
- A registry does not itself grant trust.
- A Trust Policy grants trust over registered or self-contained keys.
- A key can be present in a registry but not trusted by local policy.
- A key can be active, revoked, or retired in the registry, with optional validity-window and rotation metadata.
- Registry signature provenance is local: Trust Policy v1 decides whether a registry signing authority is trusted for a registry id.
- Registry-backed trust still requires a valid Run Manifest signature.

## Resolution Rules

To resolve a manifest signature:

1. `payload.backend_id` must identify a registry backend.
2. `payload.backend_version` must be listed if the backend declares versions.
3. `payload.profile_id` and `payload.profile_version` must be listed if profiles are declared.
4. The signature `key_id` must exist under the resolved backend.
5. If the signature contains `public_key`, it must match the registry key.
6. Registry key status must be `active`.

For alpha key lifecycle:

- `active` keys can resolve if validity windows permit.
- `revoked` keys fail.
- `retired` keys can be treated as `legacy_valid` only when manifest `created_at` is inside the validity window; absent time is indeterminate/untrusted for signed-conformance.
- `rotated_to` is validated as same-backend metadata but does not yet trigger delegation or successor-chain logic.

Failures are reported with `BACKEND_IDENTITY_*` error codes.

## Claim Boundary

Signed registry provenance is not global PKI, hardware attestation, a trusted timestamp service, or proof of physical execution. Alpha registries may be local, private, or test-only.

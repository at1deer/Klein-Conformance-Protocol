# Attestation Profile v1

Attestation Profile v1 defines where future backend or hardware attestation evidence plugs into KCP.
It is a schema and validation boundary in current alpha, not a hardware attestation proof.

## Scope

`CURRENT_ALPHA`:

- attestation profile and statement schemas;
- `none` and `mock` attestation statements only;
- validation of statement shape and binding to subject hashes or backend identity;
- no TPM, TEE, SGX, SEV, quote, enclave, PCR, or secure-element validation;
- no hardware attestation proof;
- no hardware identity proof.

`TARGET_V1`:

- recorded hardware attestation statement format;
- backend identity binding;
- verifier integration with trust policy and backend registry;
- optional bundle or recorded-run inclusion.

`LONG_HORIZON`:

- hardware attestation under explicit trust roots and threat model;
- integration with trusted timestamps and physical evidence.

## Attestation Profile Shape

```json
{
  "attestation_profile_version": "klein.attestation_profile.v1",
  "profile_id": "mock-attestation-alpha",
  "profile_kind": "mock_none",
  "hardware_attestation_claimed": false,
  "allowed_statement_kinds": ["none", "mock"],
  "requires_hardware_root": false,
  "trust_roots": [],
  "limitations": [
    "Mock/null attestation profile only.",
    "No hardware attestation proof is claimed."
  ]
}
```

Rules:

- `profile_kind: "mock_none"` is the only current-alpha profile kind.
- `hardware_attestation_claimed: true` fails strict current-alpha validation.
- `requires_hardware_root: true` fails strict current-alpha validation.
- `trust_roots` must be empty in current alpha.
- `allowed_statement_kinds` may contain only `none` and `mock` in current alpha.

## Attestation Statement Shape

```json
{
  "attestation_statement_version": "klein.attestation_statement.v1",
  "statement_id": "mock-attestation-001",
  "statement_kind": "mock",
  "subject": {
    "subject_type": "backend",
    "subject_id": "opendrop_ewod_dry_run",
    "subject_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  },
  "backend": {
    "backend_id": "opendrop_ewod_dry_run",
    "backend_version": "0.1.0-alpha"
  },
  "hardware_attestation_claimed": false,
  "hardware_root": null,
  "quote": null,
  "measurements": [],
  "signature": null,
  "metadata": {}
}
```

Rules:

- `statement_kind: "none"` or `"mock"` are the only current-alpha statement kinds.
- `subject.subject_hash`, when present, must be a `sha256:<hex>` reference.
- Attestation statements bind to a subject, backend id, or subject hash, not raw mutable content.
- `hardware_attestation_claimed: true` fails strict current-alpha validation.
- `hardware_root` must be `null` in current alpha.
- `quote` must be `null` in current alpha.
- `signature` must be `null` for `none` and `mock` current-alpha statements.
- `measurements` must be empty in current alpha.

## Attestation Status Vocabulary

KCP uses these attestation statuses:

- `not_present`: no attestation statement exists.
- `not_evaluated`: attestation material was not evaluated.
- `none`: an explicit no-attestation statement exists.
- `mock`: a valid mock attestation statement exists.
- `invalid`: attestation material is malformed or does not bind to the target.
- `attested_future`: reserved for future hardware attestation profiles; not emitted as hardware
  attestation proof in current alpha.

Current alpha must not emit a status that claims hardware attestation proof for `none` or `mock`
statements.

## Integration Boundary

This pass does not change Run Bundle v1, Run Manifest v1, HAIL v1, or Recorded Device Run v1 shapes.
Future profiles may add optional detached attestation statement entries such as
`evidence/attestation_statement.json` or recorded-run attestation statement archives. Until then,
attestation profile/statement validation is standalone.

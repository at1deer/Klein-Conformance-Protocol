# Trusted Timestamp Profile v1

Trusted Timestamp Profile v1 defines where timestamp evidence plugs into KCP. It is a schema and
validation boundary in current alpha, not a trusted timestamp proof.

## Scope

`CURRENT_ALPHA`:

- timestamp profile and token schemas;
- mock/local timestamp tokens only;
- validation of token shape and target hash binding;
- no external timestamp authority validation;
- no trusted timestamp proof.

`TARGET_V1`:

- detached timestamp tokens over run bundle, run manifest, HAIL chain digest, or recorded-run
  digests;
- RFC 3161 or equivalent timestamp profile;
- verifier integration with trust policy and timestamp trust roots;
- optional bundle or recorded-run inclusion.

`LONG_HORIZON`:

- trusted timestamping under explicit trust roots and threat model;
- integration with Attestation Profile v1 and physical evidence.

## Timestamp Profile Shape

```json
{
  "timestamp_profile_version": "klein.timestamp_profile.v1",
  "profile_id": "mock-local-alpha",
  "profile_kind": "mock_local",
  "trusted_time_claimed": false,
  "allowed_token_kinds": ["mock_local"],
  "requires_external_time_authority": false,
  "trust_roots": [],
  "limitations": [
    "Mock/local timestamp profile only.",
    "No trusted timestamp proof is claimed."
  ]
}
```

Rules:

- `profile_kind: "mock_local"` is the only current-alpha profile kind.
- `trusted_time_claimed: true` fails strict current-alpha validation.
- `requires_external_time_authority: true` fails strict current-alpha validation.
- `trust_roots` must be empty in current alpha.
- `allowed_token_kinds` must contain only `mock_local` in current alpha.

## Timestamp Token Shape

```json
{
  "timestamp_token_version": "klein.timestamp_token.v1",
  "token_id": "mock-token-001",
  "token_kind": "mock_local",
  "target": {
    "target_type": "run_bundle",
    "target_hash": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
    "target_canonicalization": "klein.canon.json.v1"
  },
  "claimed_time": "2026-05-18T00:00:00Z",
  "time_source": {
    "source_type": "local_clock",
    "authority_id": null
  },
  "trusted_time_claimed": false,
  "signature": null,
  "metadata": {}
}
```

Rules:

- `token_kind: "mock_local"` is the only current-alpha token kind.
- `target.target_hash` is required and must be a `sha256:<hex>` reference.
- Timestamp tokens bind to hashes, not raw mutable content.
- `claimed_time`, when present, must be a UTC timestamp ending in `Z`.
- `source_type: "tsa"` fails strict current-alpha validation.
- `trusted_time_claimed: true` fails strict current-alpha validation.
- `signature` must be `null` for mock/local current-alpha tokens.

## Timestamp Status Vocabulary

KCP uses these timestamp statuses:

- `not_present`: no timestamp token exists.
- `not_evaluated`: timestamp material was not evaluated.
- `mock`: a valid mock/local timestamp token exists.
- `invalid`: timestamp material is malformed or does not bind to the target.
- `trusted_future`: reserved for future trusted timestamp profiles; not emitted as trusted proof in
  current alpha.

Current alpha must not emit a status that claims trusted timestamp proof for mock/local tokens.

## Integration Boundary

This pass does not change Run Bundle v1, Run Manifest v1, HAIL v1, or Recorded Device Run v1 shapes.
Future profiles may add optional detached timestamp token entries such as
`evidence/timestamp_token.json` or recorded-run timestamp token archives. Until then, timestamp
profile/token validation is standalone.

# Run Manifest v1

Run Manifest v1 is an external cryptographic object for lifecycle-bound HAIL streams.

It moves Klein alpha evidence from a tamper-evident HAIL event sequence to a signed run summary.
It does not prove physical execution, trusted time, hardware attestation, or certified backend
identity.

## CURRENT_ALPHA

The alpha implements:

- `manifest_version = "klein.run_manifest.v1"`
- a `payload` object built from validated HAIL with exactly one `RUN_START` and one `RUN_END`
- Ed25519 signatures over canonical JCS bytes of `manifest["payload"]`
- raw base64 Ed25519 public keys and signatures
- `klein-run-manifest create`, `verify`, and `inspect`
- fixture keys and signed manifest fixtures under `tests/fixtures`
- Trust Policy v1 authorization via `--trust-policy`
- optional Backend Identity Registry v1 identity resolution via `--backend-registry`
- optional conformance report fields when a vector declares `run_manifest_path`
- `KCP-Core-Signed-Conformance-v1` reference verification through `klein-verify-run`
- signed-conformance vector enforcement through the shared verifier for valid signature plus trusted
  policy scope

Signature verification proves only that the holder of the private key signed the payload. Backend
Identity Registry v1 can declare which backend identity published the key. Trust Policy v1 decides
whether that registered or self-contained key is locally authorized. The default CLI policy verifies
cryptographic signatures and reports `trust_status=not_evaluated`.

## Manifest Shape

```json
{
  "manifest_version": "klein.run_manifest.v1",
  "payload": {
    "run_id": "R011",
    "created_by": "klein-protocol",
    "created_at": null,
    "hail_canonicalization": "klein.canon.jsonl.v1",
    "hail_digest": "sha256:<hex>",
    "hail_chain_algorithm": "klein.hail.chain.v1",
    "hail_chain_digest": "sha256:<hex>",
    "preclose_hail_digest": "sha256:<hex>",
    "preclose_hail_chain_digest": "sha256:<hex>",
    "event_count": 7,
    "event_count_preclose": 6,
    "artifact_type": "container",
    "artifact_hash": "sha256:<hex>",
    "artifact_canonicalization": "klein.canon.json.v1",
    "profile_id": "dmf",
    "profile_version": "v1",
    "backend_id": "full_simulator",
    "backend_version": "1.0.0a0",
    "mode": "HARD",
    "substrate_capabilities_hash": "sha256:<hex>",
    "substrate_topology_hash": "sha256:<hex>",
    "substrate_fingerprint": "sha256:<hex>",
    "run_status": "SUCCESS",
    "error_code": null,
    "conformance_summary_hash": null
  },
  "signatures": [
    {
      "signature_algorithm": "Ed25519",
      "key_id": "klein-test-backend-001",
      "public_key_encoding": "base64.raw.ed25519",
      "public_key": "<base64>",
      "signature_encoding": "base64.raw.ed25519",
      "signature": "<base64>"
    }
  ]
}
```

The published JSON Schema is `schemas/run_manifest.schema.json`.

## Signature Preimage

The signature preimage is:

```text
RFC8785_JCS(manifest["payload"])
```

The raw JSON text is never signed. `manifest["signatures"]` is not included in the signed payload.
Tests use `created_at = null` for reproducibility.

## HAIL Binding

Payload construction must:

1. validate HAIL v1
2. require exactly one `RUN_START` and one `RUN_END`
3. verify `RUN_END.preclose_hail_digest`
4. verify `RUN_END.preclose_hail_chain_digest`
5. compute the full HAIL digest including `RUN_END`
6. copy artifact/profile/backend/mode/substrate fields from `RUN_START`
7. copy status/error/preclose closure fields from `RUN_END`

If lifecycle events are missing, no manifest is produced.

## TARGET_V1

Before stronger v1 claims are complete, Klein should add:

- independent verifier implementations for `KCP-Core-Signed-Conformance-v1`
- registry provenance/signing, key rotation, delegation, and multiple trust roots
- manifest vectors that cover positive and negative trust-policy behavior

## LONG_HORIZON

Run Manifest v1 is one step in the longer evidence sequence:

```text
canonical bytes
report binding
event-level lifecycle binding
event hash chain
signed run manifest
backend identity/trust policy
trusted timestamp/attestation profiles
hardware-backed evidence
real recovery under sensed divergence
```

Trusted timestamps, hardware attestation, and physical proof remain future work.

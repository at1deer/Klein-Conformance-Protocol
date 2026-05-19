# HAIL Digest and Evidence Chain v1

This spec separates the current digest machinery from the longer proof-of-execution target.

## CURRENT_ALPHA

The alpha implements:

- strict HAIL v1 validation
- Klein event ordering
- RFC 8785 / JCS per-event canonical JSON
- LF-delimited canonical JSONL bytes
- SHA-256 digest over exact canonical bytes
- conformance report fields such as `digest_actual` and `digest_expected`
- `klein-hail-canon` verifier CLI for canonicalization and digest checks
- JCS-based canonical hashes for `.klein` and `.kleinc` JSON artifacts
- conformance report input binding fields such as `input_artifact_hash` and
  `input_raw_sha256`
- full-simulator report fingerprints for declared DMF/EWOD capabilities and topology
- `RUN_START` event-level binding for v1 execution vectors, including artifact hash,
  artifact canonicalization, profile, backend, mode, and simulator substrate fingerprints when
  available
- `RUN_END` closure events for v1 execution vectors with a pre-close HAIL digest over all events
  before `RUN_END`
- terminal Klein HAIL chain v1 digests in `RUN_END.preclose_hail_chain_digest`
- `klein-hail-canon --verify-chain` and `--chain-digest` for lifecycle stream verification
- Run Manifest v1 signatures over lifecycle-bound HAIL summary payloads
- Trust Policy v1 authorization for signed-conformance manifest keys

This is integrity and comparison evidence. It is not proof that the physical world executed the
log truthfully.

## HAIL Chain v1 Algorithm

The event chain is defined over exact canonical bytes:

```text
chain_domain = b"KLEIN-HAIL-CHAIN-v1\0"
h0 = SHA256(chain_domain + b"GENESIS")
```

For each strict HAIL v1 event before `RUN_END`, in Klein HAIL canonical event order:

```text
event_bytes_i = RFC8785_JCS(event_i)
h_i = SHA256(chain_domain + h_{i-1} + b"\0" + event_bytes_i)
```

The terminal pre-close chain digest is:

```text
sha256:<hex(h_n)>
```

Rules:

- events must validate as strict HAIL v1 before chaining
- event bytes are RFC 8785/JCS canonical JSON bytes
- event order is Klein HAIL event ordering
- `RUN_END` is excluded from pre-close chain computation
- `RUN_END.preclose_hail_chain_digest` stores the terminal pre-close chain digest
- `RUN_END.preclose_hail_chain_algorithm` is `klein.hail.chain.v1`
- tools may compute a chain digest for direct HAIL streams without `RUN_END`, but those streams are
  not lifecycle-bound unless they include a valid `RUN_END`
- chain verification also checks whether the input JSONL is already in canonical event order

## TARGET_V1

Klein Core v1 should bind HAIL digests to:

- artifact hashes for `.klein` / `.kleinc` inputs (implemented for alpha JSON artifacts)
- profile identifier and profile version (reported by the v1 harness)
- substrate capability and topology fingerprints (reported by the full simulator)
- run metadata that is intentionally part of the evidence contract
- conformance report schema version
- mandatory `RUN_START` / `RUN_END` lifecycle events for execution vectors
- direct-HAIL validation streams remain exempt unless they explicitly represent execution
- terminal event-chain digests for execution vectors
- signed run manifests for the signed-conformance profile
- trust-policy verification for backend/profile scoped signing keys

The verifier must be able to reproduce the digest from canonical HAIL JSONL bytes and compare it
against conformance reports or declared expected digests.

## LONG_HORIZON

Cryptographic proof/evidence chains still require more machinery:

- mature signed-conformance manifest profiles
- backend identity registry and trust policy
- substrate capability fingerprint binding
- optional trusted timestamp profile
- optional hardware attestation profile
- third-party verifier implementations

The SHA-256 payload digest is the foundation for this chain. It is not the whole chain.

## Verifier Requirements

A verifier claiming `klein.canon.jsonl.v1` compatibility must:

1. reject malformed JSONL
2. reject duplicate object names
3. reject strict HAIL v1 schema violations
4. canonicalize each event using RFC 8785 / JCS
5. order events using Klein HAIL ordering
6. compute SHA-256 over exact canonical JSONL bytes
7. compute `klein.hail.chain.v1` terminal chain digests when asked
8. compare `RUN_END.preclose_hail_chain_digest` when `RUN_END` is present
9. report digest/chain mismatches without attempting physical interpretation

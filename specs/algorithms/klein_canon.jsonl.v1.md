# Klein Canonicalization Algorithm: `klein.canon.jsonl.v1`

**Version:** 1.0 alpha target

## 1. Purpose

`klein.canon.jsonl.v1` defines the canonical byte representation for HAIL v1 evidence streams.
Its target form is:

```text
HAIL v1 validation
+ HAIL v1 field normalization
+ deterministic Klein event ordering
+ RFC 8785 / JSON Canonicalization Scheme serialization per event
+ LF-delimited JSONL bytes
+ SHA-256 digest over the exact canonical bytes
```

The digest is a stable integrity and comparison input. It is not, by itself, proof that a
physical substrate executed correctly. Proof-of-execution claims require the digest-chain,
signature, identity, timestamp, and attestation machinery described in
`specs/core/hail-digest-chain-v1.md`.

## 2. Input Requirements

Before serialization, each event MUST validate against strict HAIL v1.

Strict v1 rejects:

- unknown HAIL event kinds
- undeclared event fields
- legacy-only field names such as `rsb_hash`, `fields`, `valid_from_t`, and `valid_to_t`
- `NaN`, `Infinity`, and `-Infinity`
- duplicate JSON object names
- non-string object names
- lone UTF-16 surrogate code points

Legacy aliases may be accepted only by an explicit legacy adapter before strict v1 validation.

## 3. Event Ordering

Canonical streams sort events by this tuple:

```text
(t, event_kind_rank, kind, kind_specific_tie_breaker)
```

Event-kind ranks:

| Rank | Kind |
| --- | --- |
| 0 | `RUN_START` |
| 10 | `DEVICE_EVENT` |
| 20 | `RUNTIME_STATE_SNAPSHOT` |
| 30 | `MEASUREMENT` |
| 40 | `ECRP_ATTEMPT` |
| 50 | `REPLAN_DECISION` |
| 80 | unknown legacy kinds in explicit legacy mode only |
| 90 | `RUN_END` |

Tie breakers:

| Kind | Tie-Breaker Field |
| --- | --- |
| `RUN_START` | `run_id` |
| `MEASUREMENT` | `measurement_id` |
| `REPLAN_DECISION` | `checkpoint_id` |
| `ECRP_ATTEMPT` | `attempt_index` |
| `DEVICE_EVENT` | `code` |
| `RUNTIME_STATE_SNAPSHOT` | `rimgb_hash` |
| `RUN_END` | `run_id` |

`RUNTIME_STATE_SNAPSHOT` uses `rimgb_hash` in v1. `rsb_hash` is legacy terminology and is not
valid strict v1 input.

## 4. Per-Event JSON Serialization

Each sorted HAIL event is serialized using RFC 8785 / JCS canonical JSON:

- object properties are sorted by UTF-16 code units
- arrays preserve element order
- strings use deterministic JSON escaping and UTF-8 output
- numbers use ECMAScript/JCS number serialization
- `NaN` and infinities are invalid
- no insignificant whitespace is emitted
- duplicate object names are invalid

Examples:

```json
{"b":2,"a":1}
```

canonicalizes to:

```json
{"a":1,"b":2}
```

```json
{"n":1.0,"small":0.000001,"tiny":0.0000001}
```

canonicalizes to:

```json
{"n":1,"small":0.000001,"tiny":1e-7}
```

## 5. JSONL Byte Stream

Serialized events are joined with LF (`0x0a`) bytes. The canonical payload has no trailing extra
line unless a containing artifact explicitly declares one. The reference digest is computed over
the exact canonical bytes.

```text
canonical_event_0 LF canonical_event_1 LF canonical_event_2
```

## 6. Digest

The HAIL JSONL digest is:

```text
sha256(canonical_jsonl_bytes)
```

The digest may be embedded in conformance reports and verifier output as lowercase hex, optionally
prefixed as `sha256:<hex>`.

## 7. Reference Implementation Status

The Python alpha now provides an internal JCS serializer behind:

- `klein.hail.canonical.canonicalize_json_value`
- `klein.hail.canonical.canonicalize_hail_event`
- `klein.hail.canonical.canonicalize_hail_jsonl`
- `klein.hail.canonical.digest_hail_jsonl`
- `klein.common.hashing.canonical_json_bytes`
- `klein.common.hashing.hash_json_artifact`

The verifier CLI is:

```bash
klein-hail-canon input.jsonl --digest
klein-hail-canon input.jsonl --check expected.jsonl
klein-hail-canon input.jsonl --check-digest sha256:<hex>
```

Cross-language implementations MUST match the canonical fixture bytes and digests before claiming
`klein.canon.jsonl.v1` compatibility.

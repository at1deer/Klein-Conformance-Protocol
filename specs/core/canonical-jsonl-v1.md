# Canonical JSONL v1

Klein Canonical JSONL v1 is the HAIL stream canonical form used for exact comparison,
stable digests, and verifier input.

The target and current alpha implementation are RFC 8785 / JSON Canonicalization Scheme
serialization per event, after strict HAIL v1 validation and deterministic HAIL event ordering.

Canonical HAIL comparison sorts events by:

1. `t`
2. explicit HAIL event-kind rank
3. `kind`
4. kind-specific tie breaker

Event-kind rank:

1. `RUN_START`
2. `DEVICE_EVENT`
3. `RUNTIME_STATE_SNAPSHOT`
4. `MEASUREMENT`
5. `ECRP_ATTEMPT`
6. `REPLAN_DECISION`
7. unknown legacy kinds in explicit legacy mode only
8. `RUN_END`

Tie breakers:

- `RUN_START`: `run_id`
- `MEASUREMENT`: `measurement_id`
- `REPLAN_DECISION`: `checkpoint_id`
- `ECRP_ATTEMPT`: `attempt_index`
- `DEVICE_EVENT`: `code`
- `RUNTIME_STATE_SNAPSHOT`: `rimgb_hash`
- `RUN_END`: `run_id`

Each sorted event is serialized as JCS canonical JSON:

- UTF-16 object-property ordering
- deterministic string escaping with UTF-8 output
- ECMAScript/JCS number serialization
- no insignificant whitespace
- no duplicate object names
- no `NaN`, `Infinity`, or `-Infinity`

Canonical JSONL bytes are LF-delimited and have no trailing extra line unless an enclosing
artifact explicitly declares one. SHA-256 over these exact bytes is a comparison/integrity digest,
not by itself proof of physical execution.

Klein JSON artifacts such as `.klein` and `.kleinc` use the related
`klein.canon.json.v1` form: parse as I-JSON with duplicate-name and non-finite-number rejection,
serialize using RFC 8785 / JCS, then hash the exact canonical bytes. External report fields use
`sha256:<hex>` references.

Raw run output may include run-specific metadata. Normalized canonical payloads may replace
run-specific identifiers before digesting only when the comparison contract explicitly allows it.
The v1 conformance harness only normalizes run metadata when a vector declares
`normalize_run_metadata: true`.

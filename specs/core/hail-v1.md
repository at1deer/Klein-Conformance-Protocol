# HAIL v1

HAIL is the Hardware Audit & Integrity Log. A HAIL stream is JSONL, one event per line.

All v1 events require:

- `kind`
- `t`
- `timebase`
- `run_id`

## Event Kinds

- `RUN_START`: binds an execution HAIL stream to its declared artifact hash, artifact
  canonicalization, profile, backend, mode, and any declared substrate fingerprints available to
  the backend.
- `DEVICE_EVENT`: requires `code`, `level`, and `message`; optional `detail`.
- `MEASUREMENT`: requires `detector_id` and typed `value`. Observation Snapshot v1 is a separate
  structured observation artifact in current alpha; this pass does not change the HAIL event shape.
- `ECRP_ATTEMPT`: requires `attempt_index`, `strategy`, `outcome`, and `deltas`. ECRP Contract v1 validates attempt ordering, strategy authorization, terminal failure evidence, and policy-approved simulator retry success without changing this event shape.
- `REPLAN_DECISION`: requires checkpoint, solver, seed, and `inputs_ref`.
- `RUNTIME_STATE_SNAPSHOT`: requires `rimgb_hash`, `state_fields`, and `validity_window`.
- `RUN_END`: closes an execution HAIL stream with `status`, optional `error_code`, and a
  `preclose_hail_digest` plus `preclose_hail_chain_digest` over the stream before `RUN_END` is
  appended.

Direct HAIL validation vectors validate the supplied stream as-is. They are not wrapped with
`RUN_START` / `RUN_END` unless they explicitly represent an execution run.

## Event Ordering

HAIL v1 canonical ordering sorts by tick, then by explicit event-kind rank, then by kind-specific
tie-breaker:

1. `RUN_START`
2. `DEVICE_EVENT`
3. `RUNTIME_STATE_SNAPSHOT`
4. `MEASUREMENT`
5. `ECRP_ATTEMPT`
6. `REPLAN_DECISION`
7. unknown legacy kinds in explicit legacy mode only
8. `RUN_END`

`RUN_START` at `t=0` canonicalizes before other `t=0` events. `RUN_END` canonicalizes after other
events at its final tick.

## RUN_END Digest Semantics

`RUN_END.preclose_hail_digest` is computed over canonical HAIL JSONL bytes for every event before
`RUN_END`, including `RUN_START`. This avoids a circular digest. Report-level `digest_actual` is
computed over the full canonical HAIL stream including `RUN_END`.

`RUN_END.preclose_hail_chain_digest` is the terminal `klein.hail.chain.v1` digest over the same
pre-close event set. The chain algorithm is domain-separated and hashes each canonical event with
the previous chain digest. It is tamper-evident evidence, not a signature or physical proof.

Legacy names such as `LCP_ATTEMPT`, `lcp_id`, `rsb_hash`, `fields`, `valid_from_t`, and
`valid_to_t` are not v1 HAIL. They may be converted only by an explicit legacy adapter.

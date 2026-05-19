# ECRP Retry/Replan Contract v1

ECRP Retry/Replan Contract v1 defines how Klein records bounded recovery decisions.

Current alpha implements policy-bound failure evidence and validation. Successful closed-loop
recovery remains TARGET_V1. Hardware recovery, HIL support, trusted timestamps, and physical truth
are not claimed.

Principles:

- No invisible repair.
- No unlogged retry.
- No post-hoc success mutation.
- No recovery claim without explicit evidence.

## Definitions

- recovery policy: a canonical JSON policy controlling allowed attempts and strategies
- recovery attempt: one logged `ECRP_ATTEMPT` HAIL event
- retry: an attempt to reissue or adjust a step under policy bounds
- replan: a plan change after a fault; current HARD alpha does not allow it by default
- terminal failure: explicit failure evidence after unsuccessful attempts
- strategy: declared recovery action vocabulary
- evidence requirement: required HAIL and trace records for recovery behavior

## Policy Shape

```json
{
  "ecrp_policy_version": "klein.ecrp_policy.v1",
  "policy_id": "bounded-failure-alpha",
  "mode": "HARD",
  "max_attempts": 1,
  "allowed_strategies": ["NUDGE_PULSE", "NO_CHANGE"],
  "allow_replan": false,
  "allow_success_after_replan": false,
  "requires_trace_evidence": true,
  "terminal_failure_required": true
}
```

## Execution Mode Rules

- `HARD`: no unplanned replan. Retry behavior must be deterministic and policy-bound.
- `ENVELOPE`: bounded retry/replan may be allowed when explicitly declared by policy.
- `DIAGNOSTIC`: diagnostic attempts may be logged but do not establish authoritative success.

## Strategy Vocabulary

Current alpha strategies:

- `NUDGE_PULSE`
- `NO_CHANGE`
- `RETRY_SAME_STEP`
- `ABORT`

Target/future strategy:

- `REPLAN_AROUND_FAULT`

`REPLAN_AROUND_FAULT` requires `allow_replan: true` and is not a successful recovery claim in
current alpha.

## Evidence Requirements

- Every recovery attempt MUST emit `ECRP_ATTEMPT`.
- `attempt_index` MUST start at 1 and increase by 1.
- Attempt count MUST NOT exceed `max_attempts`.
- `strategy` MUST be listed in `allowed_strategies`.
- Terminal failure MUST be explicit when attempts do not succeed and policy requires it.
- Success after replan is invalid unless policy permits replan and success-after-replan.
- Trace evidence MUST include failed or retry steps when `requires_trace_evidence` is true.

## Trace / Runbook Relationship

Recovery attempts reference the planned/issued execution context through runbook and trace step
records. Retry/replan MUST NOT mutate the original runbook silently. Extra recovery trace steps are
allowed only when policy permits them.

## Simulated Closed-Loop Recovery Alpha

The first supported recovery-success path is simulator-only:

- DMF transient frame/channel failure recovered by `NUDGE_PULSE` retry.
- The fault is injected by the simulator and deterministically fails the target frame once.
- `NUDGE_PULSE` clears the simulated transient fault and retries the same runbook step.
- ECRP policy MUST set `allow_success_after_retry: true`.
- `allowed_success_strategies` MUST include `NUDGE_PULSE`.
- HAIL MUST include the original failure event, an `ECRP_ATTEMPT` with `outcome: "SUCCESS"`,
  and a `RUN_END` with `status: "SUCCESS"`.
- Execution Trace v1 MUST include the failed original step, recovery attempt evidence, and a
  successful retry tied to the original `runbook_step_id`.
- Observation Snapshot v1 MAY be required by policy or conformance level to confirm simulator
  state after the retry.

This is not hardware recovery, HIL recovery, physical sensor proof, arbitrary path planning,
trusted timestamp evidence, or hardware attestation.

## Forbidden Claims

ECRP Contract v1 does not claim physical recovery, unobserved success, hardware proof, HIL support,
or physical truth.

# Execution Trace v1

Execution Trace v1 is the actual issued/applied execution path recorded by a backend during a run.

It is not the canonical evidence log. HAIL remains the canonical evidence log. A trace can be used
to compare execution behavior against a Runbook v1 plan and to support future recovery decisions.

ECRP recovery metadata, when present, is carried in trace step `details` fields such as
`recovery_attempt_id`, `recovery_parent_step_id`, `recovery_strategy`, `retry_of_step_id`,
`replan_id`, and `recovery_status`. These fields do not mutate the original runbook and are valid
only when an ECRP policy allows the corresponding recovery behavior.

For the simulator-only DMF transient recovery alpha, a valid recovery-success trace records:

- the original runbook step as `FAILED`;
- a recovery attempt step with `recovery_strategy: "NUDGE_PULSE"`;
- a retry step with `recovery_status: "success"` and `retry_of_step_id` pointing at the original
  runbook step.

## Shape

```json
{
  "trace_version": "klein.execution_trace.v1",
  "trace_id": "optional-id",
  "run_id": "run-001",
  "runbook_hash": "sha256:<hex>",
  "artifact_hash": "sha256:<hex>",
  "profile": {
    "profile_id": "dmf",
    "profile_version": "v1"
  },
  "backend": {
    "backend_id": "full_simulator",
    "backend_version": "1.0.0a0"
  },
  "timebase": "DEVICE_TICKS",
  "trace_steps": [
    {
      "step_id": "step-0001",
      "runbook_step_id": "step-0001",
      "tick": 0,
      "operation": "DMF_SET_CHANNELS",
      "issued": true,
      "applied": true,
      "status": "APPLIED",
      "error_code": null,
      "details": {}
    }
  ],
  "metadata": {}
}
```

## Rules

- `trace_version` MUST be `klein.execution_trace.v1`.
- `runbook_hash` MUST identify the planned Runbook v1 artifact used for comparison.
- `artifact_hash` MUST identify the intended executable artifact.
- `trace_steps` MUST be deterministic and sorted by `tick` and then `step_id`.
- `status` MUST be one of `APPLIED`, `SKIPPED`, or `FAILED`.
- A failed step is valid trace data only if `status` is `FAILED`, `applied` is false, and
  `error_code` is present.
- Trace JSON is parsed as I-JSON and hashed with `klein.canon.json.v1`.

Trace v1 does not prove physical truth, sensor observation, closed-loop recovery, HIL readiness,
trusted timestamps, or hardware attestation.

Observation Snapshot v1 may reference trace step IDs to compare reported simulator state against
issued/applied execution. Trace remains execution detail; observation remains reported state.

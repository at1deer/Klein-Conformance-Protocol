# Runbook v1

Runbook v1 is the planned execution schedule derived from an intended artifact, profile, mode, and
substrate context.

It is a plan, not evidence. It does not prove that a backend issued or applied any operation. HAIL
remains the canonical evidence log.

ECRP Retry/Replan Contract v1 may reference runbook step IDs when validating retry or replan
evidence. Recovery validation MUST NOT silently mutate a Runbook v1 plan; recovery steps belong in
Execution Trace v1 evidence and HAIL `ECRP_ATTEMPT` events.

## Shape

```json
{
  "runbook_version": "klein.runbook.v1",
  "runbook_id": "optional-id",
  "source_artifact_hash": "sha256:<hex>",
  "source_artifact_type": "project",
  "profile": {
    "profile_id": "dmf",
    "profile_version": "v1"
  },
  "mode": "HARD",
  "substrate_fingerprint": null,
  "timebase": "DEVICE_TICKS",
  "planned_steps": [
    {
      "step_id": "step-0001",
      "tick": 0,
      "operation": "DMF_SET_CHANNELS",
      "payload_ref": "payload-001",
      "frame_ref": null,
      "expected_effect": {
        "type": "simulated",
        "details": {}
      }
    }
  ],
  "metadata": {}
}
```

## Rules

- `runbook_version` MUST be `klein.runbook.v1`.
- `source_artifact_hash` MUST be the canonical hash of the `.klein` or `.kleinc` input artifact.
- `source_artifact_type` MUST be `project` or `container`.
- `profile.profile_id` and `profile.profile_version` MUST identify the profile used to build steps.
- `mode` MUST be `HARD`, `ENVELOPE`, or `DIAGNOSTIC`.
- `timebase` MUST be `DEVICE_TICKS` in current alpha.
- `planned_steps` MUST be deterministic and sorted by `tick` and then `step_id`.
- Runbook JSON is parsed as I-JSON and hashed with `klein.canon.json.v1`.

Current alpha supports DMF operation names:

- `DMF_SET_CHANNELS`
- `DMF_APPLY_FRAME`
- `DMF_APPLY_BITMAP`

Runbook v1 does not claim physical truth, sensor observation, recovery, HIL readiness, trusted
timestamps, or hardware attestation.

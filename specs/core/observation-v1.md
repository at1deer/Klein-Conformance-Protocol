# Observation v1

Observation v1 defines simulator-backed observation snapshots for Klein execution evidence.

Trace records what a backend issued or applied. Observation records what a declared source reported
about substrate state. HAIL remains the canonical evidence log. Attestation is future proof that an
observation came from a trusted physical source.

## Scope

`CURRENT_ALPHA` supports simulator-backed observation snapshots and comparison against runbook and
trace identifiers. It does not support hardware sensor proof, HIL execution, trusted timestamps,
hardware attestation, or physical truth. HIL Readiness v1 may declare an interface capable of
returning observations, but current alpha observations remain simulator/mock evidence only.
Recorded Device Run v1 may archive observation snapshots by hash as part of a run package; this
archival binding does not change the observation source model.

`TARGET_V1` includes profile-specific observation schemas, observation-bound recovery evidence,
optional bundle inclusion, and manifest/RUN_START binding.

`LONG_HORIZON` includes hardware sensor evidence, hardware attestation, trusted timestamps, and
physical observation proof.

## Snapshot Shape

```json
{
  "observation_version": "klein.observation_snapshot.v1",
  "observation_id": "obs-0001",
  "run_id": "run-001",
  "timebase": "DEVICE_TICKS",
  "tick": 0,
  "profile": {
    "profile_id": "dmf",
    "profile_version": "v1"
  },
  "source": {
    "source_type": "simulator",
    "source_id": "full_simulator",
    "source_version": "1.0.0a0",
    "attestation": null
  },
  "observation_model": "simulated",
  "confidence": 1.0,
  "runbook_step_id": "step-0001",
  "trace_step_id": "step-0001",
  "state": {
    "dmf": {
      "active_channels": [1, 2, 3],
      "active_tiles": [[1, 0], [2, 0], [3, 0]]
    }
  },
  "metadata": {}
}
```

## Policy Shape

```json
{
  "observation_policy_version": "klein.observation_policy.v1",
  "policy_id": "simulated-dmf-alpha",
  "required_for_recovery_success": true,
  "allowed_sources": ["simulator"],
  "allowed_observation_models": ["simulated"],
  "requires_trace_alignment": true,
  "requires_runbook_alignment": false,
  "requires_attestation": false
}
```

## Rules

- `source_type: "simulator"` is valid for `CURRENT_ALPHA`.
- `source_type: "hardware_sensor"` is target/future unless a future hardware profile implements it.
- Simulator observations MUST have `attestation: null`.
- `confidence` MUST be in `[0, 1]`.
- Simulated `confidence: 1.0` means simulator-state certainty, not physical certainty.
- If policy requires trace alignment, `trace_step_id` MUST exist in the trace.
- If policy requires runbook alignment, `runbook_step_id` MUST exist in the runbook.
- Recovery success may require at least one aligned observation when policy declares it.

Observation v1 does not prove physical droplet motion, wet-lab execution, hardware observation, HIL
readiness, sensor attestation, or physical truth.

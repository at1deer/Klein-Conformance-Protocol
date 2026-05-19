# DMF/EWOD Profile v1 Alpha

DMF/EWOD Profile v1 alpha is Klein's first concrete substrate profile. It defines digital
microfluidic electrowetting-on-dielectric payload and capability semantics for the current
reference simulator.

This profile is simulator-backed in `CURRENT_ALPHA`. It does not claim HIL support, certified
hardware capability, hardware attestation, trusted timestamps, physical truth, or real
closed-loop recovery.

## Scope

The alpha profile covers:

- substrate capability declarations for a virtual DMF grid
- channel/electrode addressing
- tick-ordered actuation payloads
- sparse, bitmap, and delta frame forms
- simulated observations and bounded ECRP evidence

Hardware observation semantics, HIL levels, and recovery under sensed divergence remain
`TARGET_V1` or `LONG_HORIZON`.

HIL Readiness v1 now defines the interface boundary a future DMF hardware backend must satisfy.
Current alpha only validates contract/status artifacts and a mock operation shape; it does not claim
DMF hardware execution, HIL execution, sensor proof, or hardware attestation.

Generic DMF Backend Adapter v1 now defines the dry-run adapter skeleton for translating DMF runbooks
into adapter commands, trace steps, mock observations, raw logs, and recorded-run packages. This is
adapter structure only; OpenDrop/EWOD protocol details and real hardware IO remain target work.

OpenDrop / EWOD Adapter Skeleton v1 now defines a dry-run/config-only OpenDrop-style boundary:
config/status/command-intent shapes, electrode mapping, intent generation, raw logs, mock
observations, and mock recorded-run packages. It does not claim OpenDrop hardware IO, HIL execution,
sensor proof, physical truth, trusted timestamps, or hardware attestation.

## Addressing Model

The profile supports channel addressing over a declared electrode set.

- A `channel_id` is an integer electrode/channel id.
- A sparse pixel may be either a channel id or an `x`/`y` grid coordinate.
- Grid coordinates map to electrode id `y * grid_width + x`.
- Coordinates are valid only when `0 <= x < grid_width`, `0 <= y < grid_height`, and the mapped
  electrode id is less than `max_channels`.

The reference full simulator capability fixture declares a virtual `16 x 8` grid with
`128` channels. These are fixture capabilities, not universal DMF constants.

## Time Model

Payload time is expressed in integer ticks.

- Ticks must be integers `>= 0`.
- Frame conversion sorts entries by `t`.
- A `CHANNEL_LIST` may include multiple channel entries for the same tick.
- Conflicting states for the same `(t, channel_id)` are invalid.
- `FRAME_SEQUENCE` entries are applied in monotonic `t` order after validation.

`HARD`, `ENVELOPE`, and `DIAGNOSTIC` execution modes retain their core KCP meanings. In alpha,
the DMF profile uses the same payload validation rules for all three modes.

## Electrical Capability Model

DMF capabilities declare:

- `voltage_min_v`
- `voltage_max_v`
- `frequency_min_hz`
- `frequency_max_hz`

`voltage_min_v <= voltage_max_v` and `frequency_min_hz <= frequency_max_hz` are required.
`CHANNEL_LIST` entries must include `voltage_v`; optional `frequency_hz` must be within the
declared frequency range when present.

Out-of-range voltage and frequency are profile validation failures.

## Payload Kinds

Current alpha supports:

- `CHANNEL_LIST`
- `FRAME_SEQUENCE`
- `BITMAP_SEQUENCE`

Unsupported or malformed payload kinds are rejected. Future payload forms must be introduced by
new profile capability declarations and conformance-level updates.

## Frame Formats

`FRAME_SEQUENCE` supports:

- `sparse`: list of channel ids or grid coordinates.
- `bitmap`: strict base64 bitmap data bounded by declared channel count.
- `delta_tiles`: stateful `{ "add": [...], "remove": [...] }` sparse updates.

`rle` is explicitly unsupported in current alpha and is rejected with
`PAYLOAD_UNSUPPORTED_FRAME_FORMAT`.

## Validation Rules

Profile validation rejects:

- malformed payload shape
- unsupported payload kind
- unsupported frame format
- out-of-bounds channel id
- out-of-bounds sparse coordinate or mapped electrode
- duplicate sparse electrodes
- invalid channel state
- voltage or frequency outside declared capability range
- conflicting same-tick channel state
- invalid bitmap base64
- bitmap expansion beyond declared channel count
- `delta_tiles` add/remove conflict
- `delta_tiles` remove of inactive electrode
- substrate/capability mismatch in capability declarations

The authoritative v1 suite includes positive vectors for `CHANNEL_LIST`, sparse frames, bitmap
frames, and `delta_tiles`, plus negative vectors for malformed channel entries, out-of-bounds
channels/pixels, invalid states, electrical range failures, duplicate sparse electrodes, bitmap
base64/dimension failures, unsupported `rle`, and `delta_tiles` conflicts.

## Observability

Current alpha observations are simulated only. Runtime observations can be emitted by the
reference virtual substrate, but they are not physical sensor attestation and do not prove
physical execution.

Future observation semantics belong to `KCP-Profile-DMF-Observation-v1` or successor target
levels.

## DMF Observation Semantics

Observation v1 defines simulator-backed DMF state snapshots for current alpha:

- `active_channels`: electrode/channel IDs active in the simulated applied frame.
- `active_tiles`: `[x, y] tile coordinates derived from active channels and the simulated grid.
- `observation_model: "simulated"`: certainty about simulator state only.
- `source.source_type: "simulator"`: no hardware sensor or HIL claim.

For `CHANNEL_LIST`, `FRAME_SEQUENCE`, and `BITMAP_SEQUENCE`, the expected simulated observation
after an applied step is the set of active electrodes represented by the applied trace step and
frame event. After the simulator-only ECRP retry path, the observation is taken from the successful
retry/applied state.

DMF observations in current alpha can confirm simulator state agreement between expected transition,
trace, and observation. They cannot prove physical droplet motion, wet-lab execution, hardware
sensor validity, or physical truth.

## Recovery

Current alpha may emit bounded ECRP evidence showing attempted repair/replan behavior. It does
not implement real closed-loop recovery under sensed divergence.

ECRP Retry/Replan Contract v1 validates DMF bounded failure evidence against explicit policy,
HAIL `ECRP_ATTEMPT` events, and Execution Trace v1 failed-step evidence. This is recovery law and
failure evidence, not a successful recovery claim.

Current alpha also includes one simulator-only closed-loop recovery path: a transient DMF
frame/channel failure may be recovered by a policy-approved `NUDGE_PULSE` retry. The simulator
injects and clears the transient fault deterministically; the claim is trace/HAIL-backed simulator
recovery only, not hardware recovery or physical sensor proof.

Broader replan around permanent faults remains target work.

## Canonical Error Vocabulary

DMF/EWOD profile validation uses canonical KCP error codes including:

- `PAYLOAD_MALFORMED`
- `DDI_UNSUPPORTED_PAYLOAD`
- `PAYLOAD_UNSUPPORTED_FRAME_FORMAT`
- `PAYLOAD_CHANNEL_OOB`
- `PAYLOAD_OOB_PIXEL`
- `PAYLOAD_DUPLICATE_PIXEL`
- `PAYLOAD_INVALID_STATE`
- `PAYLOAD_VOLTAGE_OOB`
- `PAYLOAD_FREQUENCY_OOB`
- `PAYLOAD_CONFLICTING_STATE`
- `PAYLOAD_BASE64_INVALID`
- `PAYLOAD_UNSUPPORTED_DIMS`
- `PAYLOAD_DELTA_CONFLICT`
- `PAYLOAD_DELTA_REMOVE_MISS`
- `DMF_CAPABILITIES_INVALID`
- `DMF_PROFILE_UNSUPPORTED`
- `DMF_SUBSTRATE_MISMATCH`

Older notes may refer to `PAYLOAD_OOB_CHANNEL` or `PAYLOAD_INVALID_BASE64`; v1 alpha uses the
established repository names `PAYLOAD_CHANNEL_OOB` and `PAYLOAD_BASE64_INVALID`.

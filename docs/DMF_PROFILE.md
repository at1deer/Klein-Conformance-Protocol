# DMF/EWOD Profile

Digital microfluidics / electrowetting-on-dielectric is the first concrete KCP substrate profile.
In KCP terms, the profile defines how a DMF payload declares electrodes/channels, timing, electrical
limits, topology, observations, recovery evidence, and adapter boundaries.

## Scope

Current alpha is simulator-backed. It validates profile payloads and runs authoritative v1 vectors
against the full simulator. It does not claim wet-lab droplet movement, hardware source proof, HIL
execution, sensor attestation, trusted timestamp proof, or hardware attestation proof.

## Payload Kinds

Current alpha supports:

- `CHANNEL_LIST`: tick-ordered channel state entries;
- `FRAME_SEQUENCE`: frame entries, including sparse coordinate forms;
- `BITMAP_SEQUENCE`: bitmap-backed frame data.

Unsupported formats fail with machine-readable error codes.

## Frame Formats

The DMF/EWOD profile covers:

- channel id addressing;
- sparse `x`/`y` coordinate addressing;
- bitmap sequence expansion;
- delta frame semantics where supported;
- explicit rejection for unsupported encodings such as `rle`.

Sparse coordinates map through declared grid dimensions. Channel and coordinate bounds are derived
from declared capabilities, not hidden board constants.

## Validation Rules

Profile validation checks:

- payload kind;
- required fields;
- tick ordering and duplicate/conflicting states;
- channel bounds;
- coordinate bounds;
- voltage and frequency ranges;
- bitmap encoding and dimensions;
- delta-frame consistency.

## Simulator Scope

The full simulator is the executable backend for current authoritative v1 conformance. It provides a
deterministic reference path for DMF/EWOD alpha vectors, not a physical truth oracle.

## Observation Semantics

Observation v1 currently supports simulator-backed DMF snapshots aligned with runbook and trace
evidence. These observations are useful evidence artifacts, not hardware sensor readings.

## Recovery Semantics

ECRP currently defines policy-bound recovery evidence. The alpha includes one simulator-only
transient recovery success path. Real recovery under sensed physical divergence remains future work.

## Adapters

Generic DMF Backend Adapter v1 is a dry-run skeleton for translating DMF runbooks to adapter command
frames, trace steps, raw logs, mock observations, and mock recorded runs.

OpenDrop/EWOD Adapter Skeleton v1 is a dry-run/config-only OpenDrop-style boundary. It validates
OpenDrop-like config/status/command intents, maps KCP channels to electrode identifiers, emits
OpenDrop-style dry-run command intents, and can generate mock recorded-run packages. It does not
control OpenDrop hardware.

OpenDrop Transport Planning v1 adds disabled `none` / `serial_experimental` transport configs and
deterministic serial-command stream fixtures. These artifacts describe how a future OpenDrop-style
transport would be represented and gated; they do not open ports, require OpenDrop, copy OpenDrop
code, or claim OpenDrop hardware support.

## Future Hardware Path

The future hardware path requires real transport, safety gates, hardware source semantics, sensor
semantics, trusted timestamps, attestation, and an explicit threat model before physical proof can be
claimed.

## Detailed Specs

- `specs/profiles/dmf/dmf-ewod-v1.md`
- `specs/profiles/dmf/dmf-backend-adapter-v1.md`
- `specs/profiles/dmf/opendrop-ewod-adapter-v1.md`
- `specs/profiles/dmf/opendrop-transport-planning-v1.md`

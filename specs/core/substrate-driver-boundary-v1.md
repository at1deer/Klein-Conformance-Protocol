# Substrate Driver Boundary v1

Klein Core is designed to reach future hardware through a small substrate driver boundary. The
boundary is profile-neutral; profile validators consume driver capabilities and topology before any
frame is submitted. Current alpha uses virtual/mock backends and dry-run adapters only.

## Required Methods

- `connect(uri)`: establish a session with a substrate backend.
- `get_capabilities()`: return declared electrical, timing, addressing, sensing, and safety limits.
- `get_topology()`: return declared electrode/carrier topology.
- `set_waveform(wf)`: set a driver waveform profile within declared capability bounds.
- `apply_frame(frame)`: minimal conformance data-plane boundary; apply one frame and return an ack.
- `run_sequence(frames, options)`: convenience batch execution over `apply_frame`.
- `read_observations(since_seq)`: return runtime observations as evidence.
- `get_health()`: report current driver/substrate health.
- `estop()`: force a stop condition.
- `reset()`: reset driver-local session state.

## Conformance Notes

- `apply_frame` is the smallest required execution primitive for v1 conformance.
- `run_sequence` is a convenience API and must not hide per-frame failure evidence.
- Observations are evidence from declared sensors, not proof that physics succeeded.
- Profile validators must use `get_capabilities()` and `get_topology()` instead of magic board
  constants.
- Drivers must not fabricate success without ack/evidence from the substrate or controller.
- Real hardware backends are future work for this alpha; the reference v1 suite uses the virtual
  substrate backend.


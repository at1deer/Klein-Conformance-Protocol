# OpenDrop / EWOD Adapter Skeleton v1

OpenDrop / EWOD Adapter Skeleton v1 defines where an OpenDrop-style EWOD backend would plug into
Klein. It is dry-run/config-only in current alpha.

It does not require OpenDrop to be installed, import vendor libraries, open USB/serial/network
transports, control voltages on a real board, read real sensors, claim HIL execution, or prove
physical droplet movement.

GaudiLabs/OpenDrop is an external open-source project. KCP current alpha does not vendor, copy, or
derive from OpenDrop firmware or controller code. Future hardware integration must review license
compatibility before copying or deriving from GPL-licensed code.

## Scope

`CURRENT_ALPHA`:

- config, status, and command-intent schemas;
- row-major and explicit electrode mapping validation;
- dry-run command-intent generation;
- trace, raw-log, mock-observation, and recorded-run generation;
- disabled OpenDrop transport planning and command-stream serialization in
  `opendrop-transport-planning-v1.md`;
- hardware IO explicitly rejected.

`TARGET_V1`:

- real OpenDrop adapter implementation;
- actual device transport behind an explicit hardware gate;
- recorded OpenDrop run packages;
- hardware observations if supported.

`LONG_HORIZON`:

- attested OpenDrop/EWOD execution under an explicit threat model.

## Config Shape

```json
{
  "adapter_config_version": "klein.opendrop_adapter_config.v1",
  "adapter_id": "opendrop-ewod-dry-run",
  "adapter_kind": "opendrop_ewod",
  "backend_id": "opendrop_ewod_dry_run",
  "backend_version": "0.1.0-alpha",
  "profile": {
    "profile_id": "dmf",
    "profile_version": "v1"
  },
  "mode": "dry_run",
  "hardware_io_enabled": false,
  "transport": {
    "transport_kind": "none",
    "endpoint": null
  },
  "electrode_layout": {
    "layout_id": "opendrop-demo-16x8",
    "grid_width": 16,
    "grid_height": 8,
    "channel_count": 128,
    "mapping": "row_major"
  },
  "electrical_limits": {
    "voltage_min_v": 0,
    "voltage_max_v": 300,
    "frequency_min_hz": 1,
    "frequency_max_hz": 50000
  },
  "safety": {
    "require_estop": true,
    "allow_hardware_io": false
  },
  "limitations": [
    "Dry-run OpenDrop/EWOD adapter skeleton only.",
    "No OpenDrop hardware IO.",
    "No physical droplet movement claimed."
  ]
}
```

Rules:

- `hardware_io_enabled: true` fails current-alpha schema validation and runtime validation.
- `transport.transport_kind` other than `none` fails current-alpha schema validation and runtime
  validation.
- `transport.endpoint` must be `null`.
- `safety.require_estop` must be `true`.
- `safety.allow_hardware_io` must be `false`.
- `mapping: "row_major"` is supported.
- `mapping: "explicit"` is allowed only with a valid `explicit_mapping` array.
- profile must be `dmf/v1`.

## Status Shape

```json
{
  "adapter_status_version": "klein.opendrop_adapter_status.v1",
  "adapter_id": "opendrop-ewod-dry-run",
  "connected": false,
  "hardware_io_enabled": false,
  "transport_status": "NONE",
  "health": "UNKNOWN",
  "emergency_stopped": false,
  "last_error_code": null
}
```

## Command Intent Shape

```json
{
  "command_intent_version": "klein.opendrop_command_intent.v1",
  "intent_id": "intent-0001",
  "tick": 0,
  "operation": "SET_ELECTRODES",
  "electrodes": [
    {
      "electrode_id": "E0001",
      "channel_id": 1,
      "x": 0,
      "y": 0,
      "state": "ON",
      "voltage_v": 120,
      "frequency_hz": 1000
    }
  ],
  "metadata": {}
}
```

Supported current-alpha intent operations are `SET_ELECTRODES`, `APPLY_FRAME`,
`CLEAR_ELECTRODES`, `ESTOP`, and `RESET`.

## Electrode Mapping

Row-major mapping is:

- `channel_id: 1` -> `x: 0`, `y: 0`, `electrode_id: "E0001"`
- `channel_id: 2` -> `x: 1`, `y: 0`, `electrode_id: "E0002"`
- `channel_id: n` -> `x: (n - 1) % grid_width`, `y: (n - 1) // grid_width`

Out-of-range channels fail. Explicit mappings fail if they contain duplicate channels, electrodes,
or coordinates.

## Bundle And Manifest Relationship

OpenDrop adapter config is not part of `.kcprun` and is not bound into Run Manifest v1 in current
alpha. Recorded Device Run v1 packages may archive an OpenDrop dry-run adapter config under
`backend/opendrop_adapter_config.json`. This pass does not change HAIL lifecycle events or bundle
shape.

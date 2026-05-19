# OpenDrop Transport Planning v1

OpenDrop Transport Planning v1 defines how KCP represents a future OpenDrop-style device transport
without enabling or claiming OpenDrop hardware support. Current alpha supports deterministic dry-run
transport-planning command-stream serialization only; no device IO is performed.

## Scope

`CURRENT_ALPHA`:

- transport planning only;
- dry-run command serialization only;
- no OpenDrop device control;
- no serial writes by default;
- no OpenDrop SDK or firmware dependency;
- no copied or vendored OpenDrop code.

`TARGET_V1`:

- experimental serial transport behind an explicit hardware gate;
- user-supplied device endpoint;
- recorded dry-run and hardware-attempt logs;
- device handshake once hardware access exists.

`LONG_HORIZON`:

- real OpenDrop HIL backend with observation, attestation, and timestamps under an explicit threat
  model.

## License Boundary

GaudiLabs/OpenDrop is an external open-source project. KCP current alpha does not vendor, copy, or
derive from OpenDrop firmware or controller code. This spec defines independent KCP command-intent and
transport-planning artifacts. Future integration work must review license compatibility before copying
or deriving from GPL-licensed code.

## Transport Config Shape

```json
{
  "transport_config_version": "klein.opendrop_transport_config.v1",
  "transport_kind": "none",
  "hardware_io_enabled": false,
  "requires_explicit_enable": true,
  "endpoint": null,
  "baud_rate": null,
  "protocol_family": "opendrop_arduino_style",
  "command_encoding": "jsonl",
  "untested_hardware_warning": true,
  "limitations": [
    "Transport planning only.",
    "No OpenDrop hardware support is claimed."
  ]
}
```

Rules:

- `transport_kind: "none"` is the default.
- `transport_kind: "serial_experimental"` is accepted only as a disabled plan in strict
  current-alpha validation.
- `hardware_io_enabled: true` fails current-alpha schema validation and runtime validation.
- `requires_explicit_enable` must be `true` for `serial_experimental`.
- `endpoint` and `baud_rate` must be `null` in current-alpha schema validation and runtime
  validation.
- `untested_hardware_warning` must be `true`.
- Transport config validation does not open ports, import OpenDrop code, or perform device IO.
- Future serial hardware transport requires a later schema/profile or explicit unsafe mode; this
  current-alpha schema is dry-run planning only.

## Serial Command Shape

```json
{
  "serial_command_version": "klein.opendrop_serial_command.v1",
  "command_id": "cmd-0001",
  "intent_id": "intent-0001",
  "tick": 0,
  "command_kind": "SET_ELECTRODES",
  "encoding": "json",
  "payload": {
    "electrodes": []
  },
  "raw_line": "{\"command\":\"SET_ELECTRODES\",\"electrodes\":[]}",
  "hardware_io_allowed": false
}
```

Rules:

- `raw_line` must be deterministic for the same intent and transport config.
- `hardware_io_allowed` must be `false` in current-alpha schema validation and runtime validation.
- Serialized command streams are artifacts, not device IO.
- Current alpha does not implement serial writes.

## Recorded-Run Relationship

Existing OpenDrop dry-run recorded runs already store full OpenDrop command intents in
`raw/device-log.jsonl` under `details.intent`. This planning spec does not change Recorded Device Run
v1. Future recorded-run packages may include an additional command stream file such as
`backend/opendrop_command_stream.jsonl` if a later schema/profile permits it.

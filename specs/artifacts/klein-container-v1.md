# Klein Container v1

`.kleinc` is the portable Klein execution container artifact. In v1 alpha it preserves the current
container shape used by the authoritative v1 suite while documenting the canonical envelope fields
that future containers should converge on.

Container artifacts are JSON I-JSON artifacts. Hashing uses `klein.canon.json.v1` over RFC
8785/JCS canonical bytes and is represented as `sha256:<hex>`.

## Current v1 Alpha Form

```json
{
  "klein_container_version": "1.0",
  "manifest": {
    "project": {
      "name": "minimal-container",
      "version": "1.0",
      "authors": ["Klein"]
    },
    "runtime": {
      "mode": "HARD",
      "target_substrate": "dmf.muxed_ewod.opendrop.v1.0"
    }
  },
  "payload": {
    "kind": "CHANNEL_LIST",
    "encoding": "JSON",
    "data": []
  }
}
```

Required fields are `klein_container_version`, `manifest`, and `payload`.

## Canonical Envelope Direction

A future-compatible container may be represented as:

```json
{
  "kind": "KLEIN_CONTAINER",
  "schema_version": "v1",
  "container_id": "example",
  "profile": {
    "profile_id": "dmf",
    "profile_version": "v1"
  },
  "mode": "HARD",
  "payloads": [
    {
      "payload_id": "payload-001",
      "payload_kind": "FRAME_SEQUENCE",
      "encoding": "json",
      "data": []
    }
  ],
  "metadata": {}
}
```

The current alpha runtime executes the current form. The canonical envelope is documented to guide
artifact portability without forcing broad vector churn.

## Validation

Container validation must:

- reject malformed JSON and duplicate JSON object names
- reject unsupported container versions
- require manifest/runtime mode
- require payload data
- validate DMF payloads with the DMF/EWOD v1 profile validator
- preserve exact error codes for negative conformance vectors

Hardware-specific behavior belongs in profiles and backend capability declarations, not in the
container format itself.

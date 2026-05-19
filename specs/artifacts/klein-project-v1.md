# Klein Project v1

`.klein` is the portable Klein project artifact. In v1 alpha it has two accepted forms:

1. the current graph-project compatibility form used by existing vectors, and
2. the canonical project envelope form used by new artifact fixtures.

Both forms are JSON I-JSON artifacts. Hashing uses `klein.canon.json.v1` over RFC 8785/JCS
canonical bytes and is represented as `sha256:<hex>`.

## Canonical Envelope Form

```json
{
  "kind": "KLEIN_PROJECT",
  "schema_version": "v1",
  "project_id": "example",
  "profile": {
    "profile_id": "dmf",
    "profile_version": "v1"
  },
  "mode": "HARD",
  "payload": {
    "kind": "CHANNEL_LIST",
    "encoding": "JSON",
    "data": []
  },
  "metadata": {}
}
```

Required fields are `kind`, `schema_version`, `project_id`, `profile`, `mode`, and `payload`.
Unknown top-level fields are forbidden.

## Compatibility Graph Form

Current v1 vectors also accept:

```json
{
  "meta": {
    "version": "1.0",
    "target_substrate": "dmf.muxed_ewod.opendrop.v1.0"
  },
  "nodes": [],
  "edges": []
}
```

This form is preserved for existing graph/geodesic vectors. Its profile is inferred by the vector
metadata and runner context rather than embedded in the artifact.

## Relationships

- `.kleinc` containers are executable packages and may embed DMF payloads directly.
- Backend Capability Declaration v1 declares which profiles and conformance levels a backend
  claims to support.
- Run Manifest v1 and `RUN_START` bind execution evidence to the canonical project hash via
  `artifact_hash`.

Project validation is schema-backed and profile payload validation is delegated to the owning
profile validator, currently DMF/EWOD v1 alpha.

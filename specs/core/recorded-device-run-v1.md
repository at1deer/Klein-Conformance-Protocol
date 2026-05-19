# Recorded Device Run v1

Recorded Device Run v1 defines the archive index for a backend or device-side run record.

A recorded run is an archival evidence package. It preserves what a backend, simulator, mock device,
or future hardware device reported. It does not by itself prove physical truth.

## Scope

`CURRENT_ALPHA`:

- simulator/mock device run archival format;
- structure and hash validation;
- optional wrapping of `.kcprun` bundles;
- optional mock HIL interactions and raw logs;
- no real hardware claim, attestation, or trusted timestamp.

`TARGET_V1`:

- real HIL backend recorded runs;
- raw device logs from hardware adapters;
- hardware observations;
- optional media/checksum metadata;
- optional timestamp tokens using Trusted Timestamp Profile v1 or a later trusted profile.

`LONG_HORIZON`:

- attested hardware-backed evidence under an explicit threat model.

## Recorded Run Shape

```json
{
  "recorded_run_version": "klein.recorded_device_run.v1",
  "recorded_run_id": "example-recorded-run",
  "source_type": "mock_hardware",
  "source_id": "mock_hil_backend",
  "source_version": "0.0.0",
  "hardware_claimed": false,
  "attestation": null,
  "trusted_timestamp": null,
  "bundle_ref": {
    "path": "run/run.kcprun",
    "sha256": "sha256:<hex>"
  },
  "artifact_hash": "sha256:<hex>",
  "runbook_hash": null,
  "trace_hash": null,
  "observation_hashes": ["sha256:<hex>"],
  "hil_contract_hash": "sha256:<hex>",
  "hil_status_hash": "sha256:<hex>",
  "raw_device_logs": [
    {
      "log_id": "log-0001",
      "path": "raw/device-log.jsonl",
      "sha256": "sha256:<hex>",
      "log_format": "jsonl",
      "source_type": "mock_hardware"
    }
  ],
  "media": [],
  "notes": []
}
```

Rules:

- `source_type: "hardware"` is reserved for target/future validation and fails strict
  `CURRENT_ALPHA` validation.
- `hardware_claimed: true` fails strict `CURRENT_ALPHA` validation.
- `attestation` and `trusted_timestamp` must be `null` in strict `CURRENT_ALPHA` validation.
- Standalone mock/local timestamp token validation is available through Trusted Timestamp Profile v1,
  but recorded-run packages do not carry non-null trusted timestamp metadata in current alpha.
- Standalone none/mock attestation statement validation is available through Attestation Profile v1,
  but recorded-run packages do not carry non-null attestation metadata in current alpha.
- Every packaged referenced file must have a SHA-256 hash.
- Referenced paths must be relative and must not contain path traversal.
- Recorded run packages are archive indexes, not proof objects.

## Package Layout

Recommended directory form:

```text
recorded_run/
  recorded_run.json
  run/
    run.kcprun
  raw/
    device-log.jsonl
  observations/
    observation-0001.json
  hil/
    hil_contract.json
    hil_status.json
  media/
    README.md
```

The recorded run package wraps `.kcprun`; it does not replace it. `.kcprun` remains the signed
portable run bundle for HAIL, manifest, trust, artifacts, and verifier evidence. Recorded Device Run
adds backend/device-side archival material above that bundle.

Generic DMF Backend Adapter v1 may create Recorded Device Run packages in dry-run/mock mode. Such
packages must keep `hardware_claimed: false`, `attestation: null`, and `trusted_timestamp: null` in
current alpha.

OpenDrop / EWOD Adapter Skeleton v1 may also create Recorded Device Run packages in dry-run/mock
mode. Those packages may include `backend/opendrop_adapter_config.json` and raw log operations named
after OpenDrop command intents, but they must still keep `source_type: "mock_hardware"`,
`hardware_claimed: false`, `attestation: null`, and `trusted_timestamp: null`.

## Raw Device Log v1

Raw Device Log v1 is JSONL. Each line is one event:

```json
{
  "raw_log_version": "klein.raw_device_log.v1",
  "event_index": 1,
  "source_type": "mock_hardware",
  "operation": "apply_frame",
  "status": "OK",
  "tick": 0,
  "details": {}
}
```

Rules:

- `event_index` is strictly monotonic starting from `1`.
- `status` is explicit: `OK` or `ERROR`.
- `ERROR` events require `error_code`.
- `source_type: "hardware"` is future unless explicitly allowed.
- Raw device logs are not canonical HAIL.
- Raw device logs may later be used to derive trace or observation artifacts.

## Validation Relationship

Recorded-run validation can optionally invoke the independent `.kcprun` verifier when a bundle is
present. Bundle verification is not required for raw recorded-run schema validation unless strict
tooling requests it. Validation reports should distinguish:

- recorded-run structure status;
- bundle presence and optional bundle verification status;
- raw-log status;
- hardware-claim status;
- attestation status;
- timestamp status.

# Demo Recorded Run

Canonical public-alpha recorded-run demo:

```text
tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
```

Validate it with:

```bash
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
```

This package archives a `.kcprun` bundle, raw mock device logs, mock observations, HIL snapshots,
and OpenDrop dry-run adapter metadata. It is mock/dry-run current-alpha evidence with
`hardware_claimed: false`.

It does not claim hardware support, HIL execution, physical truth, sensor proof, timestamp proof,
hardware attestation proof, TPM/TEE verification, or real OpenDrop control.

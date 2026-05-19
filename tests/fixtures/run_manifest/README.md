Run Manifest v1 fixtures
=======================

These fixtures exercise the alpha signed run manifest layer.

- `lifecycle_stream.jsonl` is lifecycle-bound HAIL with RUN_START/RUN_END.
- `run_manifest_unsigned_payload.json` is the exact JCS payload preimage object.
- `run_manifest_signed.json` signs that payload with the public test key in
  `tests/fixtures/crypto`.
- `trust_policy_test.json` marks that public test key trusted for the fixture
  `full_simulator` / `dmf` / `v1` scope.

The signature proves only that the holder of the fixture private key signed the
payload. It does not prove hardware execution, trusted time, substrate
attestation, or a certified backend identity. `trust_status=trusted` means only
that the key is trusted under this local fixture policy.

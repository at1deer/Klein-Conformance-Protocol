# Signed-Conformance Fixtures

These fixtures exercise `KCP-Core-Signed-Conformance-v1`:

- `hail.jsonl` is the lifecycle-bound HAIL stream.
- `manifest_signed.json` is the Ed25519-signed Run Manifest v1 for that stream.
- `trust_policy.json` locally authorizes the public test key for the fixture backend/profile scope.
- `expected_result.json` is the stable JSON verifier output shape.

The crypto keys are public test keys only. "Trusted" means trusted by this fixture policy only; it does not imply hardware identity, substrate attestation, physical truth, or real-world sensor guarantees.

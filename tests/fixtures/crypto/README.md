Klein test Ed25519 keys
=======================

These keys are public, deterministic test fixtures for Run Manifest v1 tests.
`backend_test_ed25519_private.pem` is intentionally tracked for deterministic fixture signing only.

Do not use these keys for production, deployment, hardware identity, or private
backend signing. They prove fixture behavior only: a manifest was signed by the
holder of this test private key.

They do not prove that physical execution occurred, that a backend identity is
trusted, or that any substrate was hardware-attested.

`trust_policy_test.json` is also a public test fixture. It marks the test key
trusted only for fixture behavior under `full_simulator` / `dmf` / `v1`; it is
not a production identity registry or hardware-attestation policy.

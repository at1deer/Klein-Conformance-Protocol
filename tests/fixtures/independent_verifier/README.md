# Independent Verifier Fixtures

The positive independent verifier fixture is `tests/fixtures/run_bundle/valid_signed_run.kcprun`.

Negative independent verifier cases are generated deterministically in `tests/test_independent_verifier.py` from that positive bundle:

- `bundle_hash_mismatch.kcprun`
- `hail_chain_mismatch.kcprun`
- `manifest_signature_invalid.kcprun`
- `trust_policy_untrusted.kcprun`

The path-traversal negative fixture is `tests/fixtures/run_bundle/path_traversal_attack.kcprun`.

This keeps binary zip fixtures small while documenting the exact regeneration path. These fixtures are protocol verification inputs only; they do not imply hardware attestation, physical truth, or trusted timestamps.

# KCP-Core-Signed-Conformance-v1

`KCP-Core-Signed-Conformance-v1` is the named Klein Core v1 alpha level for accepting a run as signed-conformant.

It is stricter than "manifest verifies": a verifier must check the HAIL stream, lifecycle binding, hash chain, Run Manifest v1, Ed25519 signature, and Trust Policy v1 authorization before accepting the run.

## Required Checks

A run satisfies this level only if all checks pass:

1. The input artifact is hash-bound by `RUN_START.artifact_hash`. If an artifact is supplied to the verifier, its canonical artifact hash must match.
2. The HAIL stream validates as strict HAIL v1.
3. The HAIL stream canonicalizes under `klein.canon.jsonl.v1`.
4. `RUN_START` exists and binds artifact hash/type/canonicalization, profile id/version, backend id/version, mode, and substrate capabilities/topology/fingerprint where available.
5. `RUN_END` exists and binds status, error code, `preclose_hail_digest`, `preclose_hail_chain_digest`, and `event_count_preclose`.
6. The `klein.hail.chain.v1` event hash chain verifies.
7. Run Manifest v1 validates.
8. The Run Manifest payload matches the supplied HAIL stream and lifecycle events.
9. At least one Ed25519 signature verifies against canonical JCS bytes of `manifest["payload"]`.
10. If a Backend Identity Registry v1 is supplied, it resolves the manifest backend/profile/key identity and enforces key lifecycle status.
11. If strict signed-registry mode is requested, the registry has valid signed provenance from a locally trusted registry authority.
12. Trust Policy v1 authorizes at least one valid signing key for `backend_id`, `profile_id`, `profile_version`, and `manifest_version`.
13. If a conformance report is supplied, it is schema-valid and agrees with the HAIL/manifest binding fields.
14. Every failure is explicit and machine-readable.

## Reference Verifier

The Python alpha reference verifier is:

```text
klein.verifier.verify_signed_conformance(...)
klein-verify-run
```

Verifier result statuses use stable strings: `pass`, `fail`, `not_applicable`, and `not_evaluated`. The JSON output schema is `schemas/signed_conformance_result.schema.json`. Registry fields are `not_applicable`/`null` when no registry participates.

`KCP Run Bundle v1` can package all required signed-conformance inputs into a portable directory or `.kcprun` archive. Bundle verification must still call this signed-conformance verifier; bundle hashes are transport integrity checks, not replacements for signatures or HAIL chain evidence.

Independent Verifier v1 is the language-neutral contract for applying these checks to a `.kcprun` bundle without simulator, vector, or conformance-runner state.

## Does Not Claim

This level does not claim:

- hardware attestation
- trusted timestamps
- proof of physical truth
- real-world sensor guarantees
- certification of a backend beyond local Trust Policy v1 authorization

Those remain `TARGET_V1` or `LONG_HORIZON` work.

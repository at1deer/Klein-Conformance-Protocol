# Independent Verifier v1

Independent Verifier v1 is the language-neutral contract for validating a KCP Run Bundle v1 without the Python simulator, vector metadata, golden regeneration, or conformance harness.

An independent verifier consumes only a `.kcprun` archive or Run Bundle directory. It may accept an explicitly supplied trust override in a future profile, but the alpha reference verifier uses only bundled files.

## Inputs

- a `.kcprun` archive or `run.kcpbundle/` directory
- no repository-relative side files
- no `tests/vectors` metadata
- no simulator execution
- no conformance runner state

## Required Check Order

1. Bundle structure and zip safety.
2. `bundle.json` schema.
3. Bundle entry hashes.
4. HAIL JSONL parse and validation.
5. HAIL canonicalization digest.
6. HAIL event ordering.
7. HAIL lifecycle completeness.
8. `RUN_START` / `RUN_END` consistency.
9. HAIL chain verification.
10. Run Manifest v1 schema.
11. Manifest payload matches HAIL lifecycle and digests.
12. Ed25519 signature verification.
13. Optional Backend Identity Registry v1 schema if present.
14. Optional Backend Identity Registry v1 identity resolution if present.
15. Trust Policy v1 schema.
16. Trust Policy v1 authorization for backend/profile/manifest.
17. Optional conformance report schema and agreement if present.
18. Final signed-conformance verdict.

## Status Semantics

- `pass`: the check was evaluated and satisfied.
- `fail`: the check was evaluated and failed.
- `not_evaluated`: an earlier fatal check prevented evaluation.
- `not_applicable`: the check does not apply, for example an absent optional conformance report.

Bundle structure, bundle schema, entry hashes, HAIL validity, lifecycle/chain validity, manifest validity, signature validity, registry identity resolution when a registry is present, trust-policy authorization, and report agreement are fatal for `overall_status=pass`. Optional absent registries and reports are not fatal.

## Output

Independent verifier output is `klein.independent_verifier_result.v1`, defined by `schemas/independent_verifier_result.schema.json` and `specs/core/independent-verifier-result-v1.md`.

Failures must be explicit and machine-readable. Verifiers should preserve precise lower-level error codes such as `RUN_BUNDLE_HASH_MISMATCH`, `HAIL_CHAIN_MISMATCH`, `RUN_MANIFEST_SIGNATURE_INVALID`, and `TRUST_POLICY_SCOPE_MISMATCH`.

## Implementations

- Python reference alpha: `klein-verify-bundle`.
- Rust alpha slice: `verifiers/rust`, covering the cross-language fixture index and `.kcprun` bundle verification for Canonical JSON/JCS, HAIL Chain v1, Run Manifest Ed25519 signatures, Trust Policy authorization, bundle entry hashes, bundle security negatives, and schema-valid Independent Verifier result JSON.

The Rust slice is evidence that the contract is not Python-only. It now has semantic parity tests for core bundle fields, but it is not yet a complete replacement for the Python reference because broader fixture coverage, report agreement, directory bundle support, and additional language implementations remain future work.

## Does Not Prove

Independent Verifier v1 does not prove:

- hardware attestation
- physical truth
- trusted timestamp
- real-world sensor validity
- certified identity beyond Trust Policy v1 authorization

Those remain `TARGET_V1` or `LONG_HORIZON` work.

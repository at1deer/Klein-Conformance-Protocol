# KCP Run Bundle v1

KCP Run Bundle v1 is the portable transport artifact for a signed Klein run.

It packages the input artifact, HAIL stream, signed Run Manifest v1, Trust Policy v1, optional conformance report, optional signed-conformance verifier output, and bundle metadata into one directory or `.kcprun` archive.

The bundle is not the cryptographic claim object. Bundle hashes are raw entry-integrity hashes for transport. The signed Run Manifest remains the cryptographic claim object, and `KCP-Core-Signed-Conformance-v1` remains the acceptance level.

## Formats

Directory form:

```text
run.kcpbundle/
  bundle.json
  artifact/
    input.klein | input.kleinc
  hail/
    observables.jsonl
  manifest/
    run_manifest.json
  trust/
    trust_policy.json
  identity/
    backend_registry.json       optional
    backend_capabilities.json   optional
  conformance/
    report.json                 optional
    signed_conformance.json      optional
```

Archive form:

```text
<name>.kcprun
```

`.kcprun` is a zip archive with the same relative paths as the directory form.

## bundle.json

```json
{
  "bundle_version": "klein.run_bundle.v1",
  "bundle_id": null,
  "created_by": "klein-protocol",
  "created_at": null,
  "entries": {
    "artifact": "artifact/input.kleinc",
    "hail": "hail/observables.jsonl",
    "run_manifest": "manifest/run_manifest.json",
    "trust_policy": "trust/trust_policy.json",
    "backend_registry": "identity/backend_registry.json",
    "backend_capabilities": "identity/backend_capabilities.json",
    "conformance_report": null,
    "signed_conformance_report": null
  },
  "hashes": {
    "artifact": "sha256:<hex>",
    "hail": "sha256:<hex>",
    "run_manifest": "sha256:<hex>",
    "trust_policy": "sha256:<hex>",
    "backend_registry": "sha256:<hex>",
    "backend_capabilities": "sha256:<hex>",
    "conformance_report": null,
    "signed_conformance_report": null
  }
}
```

The published JSON Schema is `schemas/run_bundle.schema.json`.

## Verification

A Run Bundle verifier must:

1. reject unsupported formats
2. load `bundle.json`
3. validate `bundle.json` as Run Bundle v1
4. reject missing declared files
5. reject undeclared files in strict v1 bundles
6. verify raw SHA-256 entry hashes
7. verify signed registry provenance when a signed registry and trusted registry authorities are present, or when strict signed-registry mode is requested
8. verify backend capability declarations when `identity/backend_capabilities.json` is present
9. call the signed-conformance verifier over the bundled artifact, HAIL, manifest, trust policy, optional backend registry, optional backend capabilities, and optional conformance report
8. return explicit machine-readable errors

## Zip Security

For `.kcprun` archives, verifiers must not extract blindly. The reference verifier rejects:

- absolute member paths
- `..` path traversal
- backslash or drive-style paths
- duplicate member names
- missing declared entries
- undeclared extra files

The verifier extracts only validated declared members into a temporary local directory for signed-conformance verification.

The Rust verifier slice performs the same rejection checks for `.kcprun` archives and also rejects unsupported non-`.kcprun` inputs. Its duplicate-member check inspects raw central-directory names before handing the archive to the zip reader.

## Independent Verification

`klein-verify-bundle` is the Python alpha reference implementation of the Independent Verifier v1 contract. It consumes only the bundle path and emits `klein.independent_verifier_result.v1`.

`verifiers/rust` is the first non-Python alpha slice. It verifies the public cross-language fixtures, emits schema-valid Independent Verifier result JSON for bundles, and checks positive and negative `.kcprun` fixtures without simulator or conformance-runner state.

Independent verifiers must not depend on simulator execution, vector metadata, golden regeneration, conformance-runner internals, or repository layout.

## Claim Boundary

Run Bundle v1 is necessary for portable verification but not sufficient for physical proof. It does
not claim hardware attestation, trusted timestamps, substrate attestation, or real-world physical
truth. Trusted Timestamp Profile v1 currently validates standalone mock/local timestamp tokens; a
future bundle profile may carry detached timestamp evidence such as `evidence/timestamp_token.json`
without changing this current-alpha bundle claim.
Attestation Profile v1 currently validates standalone none/mock attestation statements; a future
bundle profile may carry detached attestation evidence such as `evidence/attestation_statement.json`
without changing this current-alpha bundle claim.

Recorded Device Run v1 is the archive layer above `.kcprun` for simulator/mock device-side logs,
HIL contract/status snapshots, observations, and future hardware-side records. It wraps a `.kcprun`
when present; it does not merge with or replace Run Bundle v1.

# Verify A Bundle

KCP Run Bundle v1 packages evidence into a portable `.kcprun` archive. The independent verifier
checks the evidence and trust bindings without running the simulator or conformance harness.

## Human Output

```bash
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

Expected shape:

```text
Independent verifier: overall_status=pass format=zip
```

## JSON Output

```bash
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun --json
```

Use JSON output for automation. It reports verifier status, checks, bindings, and trusted key ids.

## What Is Checked

The verifier checks:

- bundle schema;
- bundle entry hashes;
- artifact hash binding;
- HAIL canonicalization;
- lifecycle completeness;
- HAIL chain digest;
- Run Manifest signature;
- Trust Policy authorization;
- Backend Identity Registry resolution;
- signed registry provenance;
- signed Backend Capability Declaration;
- conformance level references and dependency closure.

## What Is Not Checked

Current alpha bundle verification does not check:

- physical truth;
- hardware execution;
- real sensor proof;
- trusted timestamp proof;
- hardware attestation proof or TPM/TEE verification.

A passing bundle means the packaged evidence and declared trust bindings are valid under current
alpha rules. It does not mean a physical substrate executed the run.

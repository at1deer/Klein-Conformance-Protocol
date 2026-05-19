# Demo Bundle

Canonical public-alpha demo bundle:

```text
tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

Verify it with:

```bash
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

Expected snippet:

```text
Independent verifier: overall_status=pass format=zip
```

This bundle demonstrates portable evidence verification, local trust policy, backend identity,
signed registry provenance, backend capabilities, and conformance-level checks. It does not prove
physical execution.

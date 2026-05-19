# Public Alpha Release Checklist

Use this checklist before tagging or publishing a public alpha.

## Validation

- Run the full validation matrix in `docs/VALIDATION_MATRIX.md`.
- Run the public demo commands in `examples/public-alpha/DEMO_COMMANDS.md`.
- Confirm `examples/public-alpha/EXPECTED_OUTPUTS.md` and
  `examples/public-alpha/VALIDATION_TRANSCRIPT.md` match current outputs.
- Confirm v1 conformance passes.
- Confirm v1 negative conformance passes.
- Confirm legacy remains report-only and is not advertised as authoritative v1 conformance.
- Confirm existing HAIL goldens do not change unexpectedly.
- Run Rust verifier fixtures and bundle verification.

## Repository Hygiene

- Run `git diff --check`.
- Review `git status --short`.
- Confirm no target/build/cache artifacts are included.
- Use clean export or GitHub-generated source archives for source handoff.
- Confirm no `.venv`, `.git`, Cargo `target`, `__pycache__`, or temporary outputs are included in
  release archives.
- Use `klein-export-clean-repo --output klein-conformance-clean.zip --dry-run` before creating a
  handoff archive.

Do not release a raw zipped working directory.

## Secrets And Keys

- Confirm no private keys are present except intentional public test fixtures and intentional test
  private keys used by the local fixture suite.
- Confirm test keys are clearly scoped as fixtures and not production credentials.
- Confirm `tests/fixtures/crypto/backend_test_ed25519_private.pem` is documented as a public
  deterministic test fixture key only, not production backend identity material.
- Review public test keys and fixture signing material before attaching demo assets.
- Confirm trust-policy and backend-registry docs do not imply global PKI.

## Claims

- Confirm `docs/CLAIMS_LEDGER.md` is current.
- Confirm `docs/CURRENT_ALPHA.md` matches the ledger.
- Confirm README non-claims are explicit.
- Confirm `docs/site/klein-public-alpha-page.md` and `docs/site/klein-demo-post.md` do not overclaim
  hardware behavior.
- Confirm `examples/public-alpha/RELEASE_ASSETS.md` identifies publishable demo assets.
- Confirm adapter docs say dry-run/config-only where appropriate.
- Confirm timestamp docs say mock/local only and do not claim TSA/RFC 3161 validation or trusted
  timestamp proof.
- Confirm attestation docs say none/mock only and do not claim TPM/TEE verification, hardware
  identity proof, or hardware attestation proof.
- Confirm no docs claim hardware support, HIL execution, physical truth, sensor proof, trusted
  timestamp proof, hardware attestation, or production certification.

## Package

- Run `python -m build`.
- Run `twine check dist/*`.
- Confirm package metadata and README render cleanly.
- Inspect dist contents before upload:
  - `python -m zipfile -l dist/klein_protocol-1.0.0a0-py3-none-any.whl`
  - `tar -tf dist/klein_protocol-1.0.0a0.tar.gz`
- Confirm the packaged wheel includes `klein/catalogs/conformance_levels.v1.json`.
- Confirm test vectors, Cargo `target`, caches, and local artifacts are not accidentally packaged.

## Release

- Tag the release after validation.
- Recommended tag for this alpha: `v1.0.0a0`.
- Attach example `.kcprun` bundles and recorded-run fixtures only if they are intended public test
  artifacts.
- Attach or link `RELEASE_NOTES.md`, `RELEASE_MANIFEST.md`, `docs/WHITEPAPER.md`, and
  `examples/public-alpha/`.
- Confirm legacy remains report-only; do not advertise the legacy corpus as authoritative v1
  conformance.

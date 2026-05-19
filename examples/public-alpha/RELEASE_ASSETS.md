# Public Alpha Release Assets

Recommended assets for a public alpha release. Do not upload a raw working-tree zip.

## Source Distribution

- Path after build: `dist/klein_protocol-1.0.0a0.tar.gz`
- Generation command: `python -m build`
- Safe to publish: yes, after release review.
- Contains test keys: source includes intentional public test fixtures only.
- Generated artifact: yes.
- Notes: run `twine check dist/*` and `tar -tf dist/klein_protocol-1.0.0a0.tar.gz` before publishing.

## Wheel

- Path after build: `dist/klein_protocol-1.0.0a0-py3-none-any.whl`
- Generation command: `python -m build`
- Safe to publish: yes, after release review.
- Contains test keys: package data should be reviewed; fixture keys are for tests only.
- Generated artifact: yes.
- Notes: inspect with `python -m zipfile -l dist/klein_protocol-1.0.0a0-py3-none-any.whl`; confirm
  `klein/catalogs/conformance_levels.v1.json` is present and test vectors are not packaged.

## Clean Repo Zip

- Suggested output: `klein-conformance-clean.zip`
- Generation command: `klein-export-clean-repo --output klein-conformance-clean.zip`
- Safe to publish: yes, after reviewing dry-run output.
- Contains test keys: includes intentional public test fixtures if present in source.
- Generated artifact: yes.
- Notes: run `klein-export-clean-repo --output klein-conformance-clean.zip --dry-run` first; use
  GitHub source archives or clean export, not a raw working-tree zip.

## Demo `.kcprun` Bundle

- Path: `tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun`
- Generation command: fixture maintained in repo.
- Safe to publish: yes, as a public test fixture.
- Contains test keys: may reference public test signing material; not production credentials.
- Generated artifact: fixture artifact.
- Notes: canonical public demo for bundle verification.

## Recorded-Run Demo Package

- Path: `tests/fixtures/recorded_run/opendrop_dry_run_recorded_run`
- Generation command: fixture maintained in repo; can also be generated with `klein-opendrop-backend create-mock-recording`.
- Safe to publish: yes, as a mock/dry-run fixture.
- Contains test keys: includes a `.kcprun` fixture; test material only.
- Generated artifact: fixture package.
- Notes: `hardware_claimed` is false; no physical execution is claimed.

## Whitepaper

- Path: `docs/WHITEPAPER.md`
- Generation command: maintained source doc.
- Safe to publish: yes.
- Contains test keys: no.
- Generated artifact: no.
- Notes: public-alpha synthesis of current architecture and claims.

## Validation Transcript

- Path: `examples/public-alpha/VALIDATION_TRANSCRIPT.md`
- Generation command: maintained transcript from validation runs.
- Safe to publish: yes.
- Contains test keys: no.
- Generated artifact: no.
- Notes: counts reflect current alpha and may change.

## Release Notes And Manifest

- Paths: `RELEASE_NOTES.md`, `RELEASE_MANIFEST.md`
- Generation command: maintained source docs.
- Safe to publish: yes.
- Contains test keys: no.
- Generated artifact: no.
- Notes: include these with release assets or link them from the release description.

## Rust Verifier Source

- Path: `verifiers/rust/`
- Generation command: source tree.
- Safe to publish: yes.
- Contains test keys: no production secrets; test fixtures are public.
- Generated artifact: no.
- Notes: demonstrates non-Python fixture and bundle verification.

## Fixture Index

- Path: `tests/fixtures/cross_language/fixtures.json`
- Generation command: maintained fixture index.
- Safe to publish: yes.
- Contains test keys: references fixture material only.
- Generated artifact: no.
- Notes: canonical cross-language verifier fixture list.

## Do Not Upload

Do not upload raw working-tree zips containing:

- `.git`
- `.venv`
- `dist/` before review
- Cargo `target/`
- `__pycache__/`
- `.pytest_cache/`
- `.ruff_cache/`
- local `.tmp/` outputs
- editor state or terminal transcript folders
- agent scratch/output folders

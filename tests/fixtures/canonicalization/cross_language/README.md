# Klein Cross-Language Canonicalization Fixtures

These fixtures are implementation-independent targets for future Rust, C++,
JavaScript, and other Klein verifiers.

Each fixture has:

- `*_input.json` or `*_input.jsonl`: source payload
- `*_expected.json` or `*_expected.jsonl`: canonical bytes interpreted as UTF-8. Repository
  text files may carry one final LF; verifier tests trim at most one final LF before comparing
  canonical bytes.
- `*_expected.sha256`: `sha256:<hex>` digest over the canonical bytes after that optional
  final-LF trim

The target algorithm is `klein.canon.json.v1` for JSON values and
`klein.canon.jsonl.v1` for HAIL streams.

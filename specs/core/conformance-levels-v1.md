# Conformance Levels v1

KCP Conformance Levels v1 defines the machine-readable claim catalog for Klein implementations.
The canonical catalog is `specs/catalogs/conformance_levels.v1.json`, and its schema is
`schemas/conformance_levels.schema.json`. A packaged copy is included at
`src/klein/catalogs/conformance_levels.v1.json` so installed CLIs can validate claims without a
source checkout; the `specs/catalogs` file remains normative.

A conformance level is a claim object with:

- `level_id`
- `name`
- `layer`: `CURRENT_ALPHA`, `TARGET_V1`, or `LONG_HORIZON`
- `category`: `core`, `profile`, `verifier`, `hardware`, or `recovery`
- `status`: `implemented`, `partial`, `target`, or `future`
- `requires`
- `required_artifacts`
- `required_checks`
- `evidence`
- `forbidden_claims`

Backend Capability Declaration v1 uses `supported_conformance_levels` to list these ids. A
verifier must reject unknown levels, future levels, target levels unless target claims are
explicitly allowed, and declarations whose dependency closure is incomplete.

Implemented levels are alpha claims backed by current specs/tests/fixtures. They do not imply
hardware attestation, certified hardware capability, trusted timestamps, physical truth, or HIL
support unless a specific implemented hardware level says so. No such hardware level exists in
v1 alpha.

Target and long-horizon levels remain visible in the catalog so the roadmap is explicit without
allowing current implementations to claim them as supported.

The DMF/EWOD profile levels are backed by `specs/profiles/dmf/dmf-ewod-v1.md`, the DMF JSON
schemas under `schemas/profiles/dmf/`, DMF profile fixtures, schema parity tests, cross-language
DMF fixtures, and targeted v1 DMF positive/negative vectors.

`KCP-Profile-DMF-Recovery-Sim-v1` is a `CURRENT_ALPHA` simulator claim only. It covers one
policy-approved transient DMF retry path and forbids hardware recovery, HIL support, sensor
attestation, and physical truth claims.

`KCP-Profile-DMF-Observation-v1` is a `CURRENT_ALPHA` simulator claim only. It covers Observation
Snapshot v1 and policy validation for simulated DMF state, plus trace alignment. It forbids hardware
observation, HIL support, sensor attestation, and physical truth claims.

`KCP-Core-HIL-Readiness-v1` is a `CURRENT_ALPHA` interface-readiness claim only. It covers HIL
Backend Contract v1, HIL Backend Status v1, mock backend operation shape, emergency-stop/reset
semantics, and CLI/fixture validation. It forbids hardware execution, HIL execution, hardware
observation proof, sensor attestation, trusted timestamps, hardware attestation, and physical truth.

`KCP-Core-Recorded-Run-v1` is a `CURRENT_ALPHA` archive-format claim only. It covers Recorded Device
Run v1, Raw Device Log v1, package hash validation, optional `.kcprun` wrapping, mock fixtures, and
cross-language shape checks. It forbids hardware execution, hardware-backed evidence, attestation,
trusted timestamps, sensor proof, and physical truth claims.

`KCP-Profile-DMF-Backend-Adapter-v1` and `KCP-Profile-DMF-DryRun-Backend-v1` are `CURRENT_ALPHA`
dry-run adapter claims only. They cover adapter config/status validation, dry-run runbook
translation, trace/raw-log/mock-observation generation, and adapter-produced recorded-run packages.
They forbid hardware IO, HIL execution, hardware support, trusted timestamps, hardware attestation,
sensor proof, and physical truth.

`KCP-Profile-DMF-OpenDrop-Adapter-Skeleton-v1` is a `CURRENT_ALPHA` dry-run/config-only adapter
claim. It covers OpenDrop-style config/status/command-intent validation, electrode mapping, dry-run
intent generation, raw-log/mock-observation output, and adapter-produced recorded-run packages. It
does not imply OpenDrop hardware support, HIL execution, sensor proof, trusted timestamps, hardware
attestation, or physical truth. `KCP-Profile-DMF-OpenDrop-HIL-v1` and
`KCP-Profile-DMF-OpenDrop-Attested-v1` remain target/future levels.

`KCP-Core-Timestamp-Profile-Stub-v1` is a `CURRENT_ALPHA` schema and validation-boundary claim only.
It covers Trusted Timestamp Profile v1 mock/local profile and token validation, canonical hashing,
target-hash binding checks, CLI tooling, and Python/Rust fixtures. It forbids trusted timestamp
proof, timestamp authority verification, hardware attestation, and physical truth claims.

`KCP-Core-TrustedTimestamp-v1` remains `TARGET_V1`. It requires an external timestamp authority or
equivalent profile, explicit trust roots, verifier integration, and a threat model before it can be
claimed as trusted timestamp proof.

`KCP-Core-Attestation-Profile-Stub-v1` is a `CURRENT_ALPHA` schema and validation-boundary claim
only. It covers Attestation Profile v1 none/mock profile and statement validation, canonical hashing,
subject/backend binding checks, CLI tooling, and Python/Rust fixtures. It forbids hardware
attestation proof, hardware identity proof, TPM/TEE verification, and physical truth claims.

`KCP-Core-AttestationProfile-v1` and future hardware-attestation levels remain target/future. They
require explicit hardware roots, quote semantics, verifier integration, trusted timestamp
integration, and a threat model before they can be claimed as hardware attestation proof.

# Klein Conformance Protocol: Evidence and Verification for Physical Execution Under Uncertainty

## Abstract

Klein Conformance Protocol (KCP) is a protocol stack for evidence, conformance, and verification of
physical-substrate execution attempts under uncertainty. It separates portable input artifacts,
planned execution, observed execution evidence, signed claims, trust policy, and independent
verification so that execution claims can be checked without depending on a single runtime or
simulator.

The current public alpha implements canonical project/container artifacts, Runbook v1, Execution
Trace v1, HAIL v1 evidence, HAIL chain digests, signed Run Manifest v1, portable `.kcprun` bundles,
local trust policy, backend identity and capability fixtures, Python and Rust verifier surfaces, a
DMF/EWOD simulator profile, dry-run Generic DMF and OpenDrop/EWOD adapter skeletons, OpenDrop
transport planning artifacts, Observation v1, HIL Readiness v1, and Recorded Device Run v1 archives. The current alpha verifies evidence artifacts, bindings, signatures, bundles, profiles, simulated runs, mock/dry-run adapters, and recorded-run packages. It **does not** prove physical execution.

## 1. The Problem: Execution Claims Across Resistant Matter

Software execution can often be replayed against a deterministic machine model. Physical-substrate
execution is different. Matter resists. Devices drift, wear, saturate, stick, heat, slip, leak, or
fail. Sensors are partial and noisy. A controller can issue a command, but the physical world may not
perform the intended transition.

That gap is decisive when a system claims that an action was executed on a substrate. The useful question is not only "what did the program request?" It is also "what artifact was used, what plan was derived, what was issued, what evidence was emitted, who signed it, what trust policy authorized it, and what can an independent verifier check?"

KCP is carefully designed around a "TCP/IP-for-matter" analogy. KCP is **not** TCP/IP for programmable matter today. It is a candidate evidence and conformance layer that such a stack needs: a way to describe inputs, profile constraints, execution attempts, failures, signatures, bundles, and verifier results across heterogeneous substrates.

## 2. Design Goals

KCP is designed around the following goals:

- **Canonical evidence**: evidence artifacts must have deterministic bytes and stable digests.
- **Portable verification**: run evidence should travel as a bundle that independent tools can
  inspect.
- **Substrate/profile separation**: core artifacts and evidence are substrate-neutral; DMF/EWOD and
  future substrates live in profiles.
- **Explicit uncertainty**: physical execution attempts can fail, diverge, or require recovery
  evidence.
- **No silent recovery**: recovery attempts must be planned, bounded, logged, and checkable.
- **No invisible repair**: a repaired or retried run should leave evidence in runbook, trace, HAIL,
  observation, or recovery artifacts.
- **Independently checkable bundles**: a verifier should not need to run the simulator or conformance
  harness to evaluate packaged evidence.
- **No overclaiming physical truth**: current alpha verifies artifacts and trust bindings; hardware
  proof requires future source semantics, timestamps, attestation, and a threat model.

## 3. Core Architecture

```text
.klein/.kleinc
    -> Runbook
    -> Execution Trace
    -> HAIL
    -> Run Manifest
    -> .kcprun Bundle
    -> Independent Verifier
```

### Artifacts

`.klein` Project v1 and `.kleinc` Container v1 are portable input artifacts. They carry declared
profiles and payloads. Current alpha validates their schema, profile metadata, payload shape, and
canonical hashes. An artifact hash proves byte-level binding to a canonical artifact value. It does
not prove execution.

### Runbook

Runbook v1 is the planned execution record derived from an artifact. It says what the runtime intends
to issue. Separating the runbook from the trace prevents a runtime from confusing "planned" with
"actually issued."

### Execution Trace

Execution Trace v1 records issued and applied steps, statuses, failures, and trace details. It
supports runbook/trace comparison and recovery evidence. A trace is execution evidence, not physical
proof.

### HAIL

HAIL v1 is the canonical event log for KCP evidence. It carries lifecycle events and other protocol
evidence with strict schema and ordering rules.

### Run Manifest

Run Manifest v1 signs lifecycle-bound evidence. In current alpha, Ed25519 signatures and local trust
policies make evidence provenance checkable. The signature covers evidence claims; it does not certify
hardware.

### Run Bundle

Run Bundle v1 packages the evidence into `.kcprun`: bundle metadata, entries, HAIL, manifests, trust
policy, registry/capability material, and hashes. It is the portable unit consumed by independent
verifiers.

### Independent Verifier

The independent verifier checks bundle integrity, evidence hashes, HAIL canonicalization, lifecycle
requirements, signatures, trust policy, backend registry, signed registry provenance, backend
capabilities, and conformance level declarations. It does not run the simulator.

## 4. HAIL and Canonical Evidence

HAIL v1 is the evidence log layer. A HAIL stream is JSONL with strict event schema validation and
deterministic canonicalization. Current alpha uses RFC 8785/JCS-style canonical JSON per event so
that independent implementations can reproduce byte sequences and SHA-256 digests.

`RUN_START` binds a run to declared input artifacts, profile/backend metadata, mode, and simulator
substrate fingerprints where applicable. `RUN_END` closes the lifecycle and carries terminal digest
evidence.

The pre-close digest covers every event before `RUN_END`. The HAIL chain digest links ordered events
so insertion, deletion, reordering, and field tampering are detectable by canonical-order and digest
checks. This gives tamper-evident evidence. It is not a signature by itself and not physical proof.

KCP is meant to support independent verification, and so uses deterministic bytes. A Python runtime, a Rust verifier, and future verifier implementations must be able to agree on what was signed and what was checked.

## 5. Trust and Identity

KCP current alpha includes a local/test trust stack:

```text
Backend Key
    -> Backend Identity Registry
    -> Signed Registry Provenance
    -> Trust Policy
    -> Signed Backend Capabilities
    -> Verified Run Claim
```

Run Manifest v1 uses Ed25519 signatures over run evidence. Trust Policy v1 decides which keys or
registry authorities are authorized for a backend/profile scope.

Backend Identity Registry v1 declares backend identities and keys. Signed registry provenance lets a
trust policy authorize registry authorities and key lifecycle status. Backend Capability Declaration
v1 states which profiles, modes, substrates, and conformance levels a backend claims.

Conformance Levels Matrix v1 gives those claims machine-readable names with dependency closure and
future/target rejection rules. A backend cannot silently claim a future level in current alpha.

This is local trust policy, not global PKI. Registry provenance is provenance for registry material,
not hardware certification. Signed backend capabilities declare local fixture capabilities; they do
not prove a physical device executed a run.

## 6. Portable Run Bundles

`.kcprun` is the portable package format for KCP run evidence. A bundle can contain artifacts, HAIL,
run manifests, trust policy, backend registries, signed registry material, backend capabilities, and
verifier-facing metadata.

Independent verification checks:

- bundle schema and entry hashes;
- artifact hash binding;
- HAIL canonicalization;
- lifecycle completeness;
- HAIL chain digest;
- Run Manifest signature;
- Trust Policy authorization;
- Backend Identity Registry resolution;
- signed registry provenance;
- signed Backend Capability Declaration;
- conformance level references and dependency closure;
- mock/local timestamp profile and token shape/binding;
- none/mock attestation profile and statement shape/binding.

The Python verifier is the reference implementation. The Rust verifier is the first non-Python slice,
covering cross-language fixtures and bundle verification without importing the Python simulator or
conformance runner.

Bundle verification checks packaged evidence and local trust bindings. It does not check physical
truth, hardware execution, real sensor proof, trusted timestamp proof, or hardware attestation.

Trusted Timestamp Profile v1 is present as a stub boundary: current alpha can validate mock/local
timestamp tokens bound to target hashes and report that the token is mock evidence. It does not
validate a TSA, RFC 3161 chain, external time authority, or trusted timestamp proof.

Attestation Profile v1 is present as a stub boundary: current alpha can validate none/mock
attestation statements bound to subject hashes or backend ids. It does not validate TPM/TEE quotes,
hardware roots, device identity, or hardware attestation proof.

## 7. DMF/EWOD Profile Alpha

Digital microfluidics / electrowetting-on-dielectric (DMF/EWOD) is the first concrete KCP profile.
It is a good early profile because it has discrete electrodes/channels, timing, voltage/frequency
constraints, frame sequences, and a clear gap between commanded actuation and physical droplet
movement.

Current alpha supports schema-backed validation for:

- `CHANNEL_LIST` payloads;
- `FRAME_SEQUENCE` payloads;
- `BITMAP_SEQUENCE` payloads;
- sparse coordinate frames;
- bitmap and delta frame forms where supported;
- explicit rejection of unsupported forms such as `rle`;
- voltage and frequency range checks;
- channel and coordinate bounds derived from declared capabilities.

The full simulator is the executable backend for authoritative v1 conformance vectors. It validates
the profile and emits evidence, but it is not a wet-lab oracle. Current profile claims are about
payload validity, simulator execution, evidence binding, and reproducible vectors.

The current alpha does **not** claim DMF hardware support, HIL execution, wet-lab droplet movement,
sensor proof, trusted timestamps, hardware attestation, or production certification.

## 8. Runbook, Trace, Recovery, Observation

Runbook and trace separation is central to KCP. The runbook records what was planned. The trace
records what was issued, applied, failed, retried, or observed. This separation keeps conformance
evidence accountable when execution diverges.

ECRP, the Error Correction & Recovery Protocol, defines policy-bounded recovery evidence. Current
alpha supports bounded failure evidence and one simulator-only transient recovery success path using
policy-approved retry evidence. Simulated recovery is not physical recovery.

Observation v1 defines observation snapshots aligned with runbook and trace evidence. Current alpha
observations are simulator-backed DMF snapshots. They are useful evidence artifacts for validating
alignment and state shape. They are not physical sensor readings and not sensor proof.

Future physical observation needs source semantics, sensor models, confidence policy, timestamps,
attestation, and threat modeling before it can support stronger claims.

## 9. HIL Readiness, Recorded Runs, and Adapters

HIL Readiness v1 defines backend contract and status artifacts for future hardware-in-the-loop
backends. It validates interface shape, declared operations, health, emergency-stop semantics, and
mock behavior. It does not claim HIL execution.

Recorded Device Run v1 defines an archive shape that can wrap `.kcprun` evidence together with raw
device logs, observations, HIL contract/status snapshots, and backend metadata. Current alpha
recorded runs are mock/dry-run archives with `hardware_claimed: false`.

Generic DMF Backend Adapter v1 is a dry-run skeleton for translating DMF runbook steps into adapter
commands, traces, raw mock logs, mock observations, and recorded-run packages.

OpenDrop/EWOD Adapter Skeleton v1 is a dry-run/config-only OpenDrop-style boundary. It validates
OpenDrop-like config/status/command intents, maps KCP channels to OpenDrop-style electrodes, emits
OpenDrop command intents, and can generate mock recorded-run packages. It imports no OpenDrop SDK,
opens no USB/serial/network transport, and controls no real hardware.

OpenDrop Transport Planning v1 defines disabled transport configs and deterministic command-stream
artifacts for a future serial path. Strict current-alpha validation rejects hardware IO, endpoints,
and baud rates. The command stream is serialized evidence only, not device control.

KCP current alpha does not copy, vendor, or derive from GaudiLabs/OpenDrop firmware or controller
code. Future hardware integration must address license compatibility before any GPL-licensed code is
copied or derived.

These layers prepare the boundary future hardware adapters need. They do not claim hardware IO, real
OpenDrop control, HIL execution, physical proof, sensor proof, trusted timestamp proof, or hardware
attestation.

## 10. Conformance and Verification Status

Current public-alpha validation includes:

- Python test suite: `439 passed, 3 skipped` in the validated environment;
- v1 conformance suite: `53 total`, `53 passed`, `0 failed`;
- v1 negative conformance: `32 total`, `32 passed`, `0 failed`;
- conformance level catalog: `39 levels`;
- Rust cross-language fixtures: `106 fixtures passed`, `0 failed`;
- legacy corpus: report-only, currently `120 total`, `2 passed`, `118 failed`, exit `1` expected.

These counts describe this repository state and may change as fixtures and tests are added. The
important distinction is stable: `tests/vectors/v1` is the authoritative v1 conformance corpus, while
the legacy corpus is migration material.

## 11. Threat Model and Limits

KCP current alpha provides tamper-evident evidence and signed provenance for local/test trust
policies. It can detect many evidence-package failures: hash mismatch, schema mismatch, missing
bundle entries, HAIL ordering problems, signature failures, trust-policy scope mismatches, backend
registry/key lifecycle failures, backend capability mismatches, and invalid conformance-level claims.

The current alpha does not provide:

- physical execution proof;
- hardware support;
- HIL execution;
- real sensor proof;
- sensor attestation;
- trusted timestamp proof;
- hardware attestation proof;
- TPM/TEE verification;
- real OpenDrop control;
- certified backend identity beyond local trust policy;
- production certification.

Future hardware evidence must separate at least four concerns: what the controller issued, what
hardware or sensors reported, when evidence was produced, and why a verifier should trust the source.
That requires hardware source semantics, trusted timestamping, attestation, and an explicit threat
model.

## 12. Roadmap

Current alpha has implemented the evidence/trust/bundle/verifier stack, the DMF/EWOD simulator
profile, runbook/trace separation, ECRP bounded recovery evidence, simulator-backed observations,
HIL readiness, Recorded Device Run archives, Generic DMF plus OpenDrop/EWOD dry-run adapter
skeletons, OpenDrop transport planning, a Trusted Timestamp Profile v1 stub, and an Attestation
Profile v1 stub.

Target V1 work includes external timestamp authority / RFC 3161-like validation beyond the mock/local
stub, real hardware attestation verification beyond the none/mock stub, real backend adapter
planning, stronger hardware source semantics, richer independent verification parity, and clearer
hardware observation contracts.

Long-horizon work includes real OpenDrop transport, first hardware runs, hardware-backed evidence,
and physical proof under a published threat model. The TCP/IP-for-matter ambition remains the
direction, but the current alpha deliberately stops at evidence artifacts, simulator/profile
validation, dry-run adapters, and independent verification of packaged claims.

## 13. Conclusion

KCP is building the evidence layer future programmable-matter systems need. It makes physical
execution claims more accountable by separating artifacts, plans, traces, evidence logs, signatures,
bundles, trust policy, profile constraints, and verifier results.

The current alpha is not physical proof. It is a working protocol skeleton for making future physical
execution claims explicit, inspectable, portable, and independently checkable.

## Claims Table

| Capability | Current Alpha Status | Evidence in Repo | Non-Claim |
| --- | --- | --- | --- |
| HAIL v1 | Implemented evidence log validation | `specs/core/hail-v1.md`, `src/klein/hail/`, `tests/test_hail_core.py` | Not a physical proof log |
| HAIL chain | Implemented tamper-evident digest chain | `specs/core/hail-digest-chain-v1.md`, `tests/test_hail_chain.py` | Not a signature or hardware attestation |
| Signed run manifest | Implemented with Ed25519 fixtures | `specs/core/run-manifest-v1.md`, `src/klein/tools/run_manifest.py` | Not trusted time or hardware certification |
| Trust Policy v1 | Implemented local authorization policy | `specs/core/trust-policy-v1.md`, `tests/test_run_manifest.py` | Not global PKI |
| Backend Identity Registry v1 | Implemented local/test registry | `specs/core/backend-identity-registry-v1.md`, `tests/test_backend_identity_registry.py` | Not a hardware root of trust |
| Signed registry provenance | Implemented for local registry authority fixtures | `tests/test_signed_backend_registry.py`, `verifiers/rust/` | Not hardware certification |
| Signed backend capabilities | Implemented for local/test capability declarations | `specs/core/backend-capability-declaration-v1.md`, `tests/test_backend_capabilities.py` | Not certified hardware capability |
| `.kcprun` bundles | Implemented portable bundle format | `specs/core/run-bundle-v1.md`, `src/klein/bundle/`, `tests/test_run_bundle.py` | Not physical execution proof |
| Python independent verifier | Implemented reference verifier | `src/klein/verifier/`, `klein-verify-bundle` | Does not run or prove hardware |
| Rust verifier | Implemented first non-Python verifier slice | `verifiers/rust/`, `tests/test_rust_verifier.py` | Not a full simulator or hardware verifier |
| DMF/EWOD simulator profile | Implemented alpha profile and simulator vectors | `specs/profiles/dmf/`, `src/klein/profiles/dmf/`, `tests/vectors/v1/` | Not wet-lab droplet proof |
| ECRP simulated recovery | Implemented bounded evidence and one simulator success path | `specs/core/ecrp-v1.md`, `tests/test_ecrp_contract.py` | Not physical recovery |
| Observation v1 | Implemented simulator-backed snapshots | `specs/core/observation-v1.md`, `tests/test_observation_semantics.py` | Not real sensor proof |
| HIL readiness | Implemented contract/status interface checks | `specs/core/hil-readiness-v1.md`, `src/klein/hil/` | Not HIL execution |
| Recorded Device Run v1 | Implemented mock/dry-run archive validation | `specs/core/recorded-device-run-v1.md`, `src/klein/recording/` | Not hardware-backed evidence |
| Generic DMF adapter | Implemented dry-run adapter skeleton | `specs/profiles/dmf/dmf-backend-adapter-v1.md`, `src/klein/backends/dmf/` | Not hardware IO |
| OpenDrop/EWOD adapter skeleton | Implemented dry-run/config-only skeleton | `specs/profiles/dmf/opendrop-ewod-adapter-v1.md`, `src/klein/backends/dmf/opendrop/` | Not real OpenDrop control |
| OpenDrop transport planning | Implemented disabled transport config and command-stream fixtures | `specs/profiles/dmf/opendrop-transport-planning-v1.md`, `schemas/profiles/dmf/opendrop_transport_config.schema.json` | Not OpenDrop hardware support |
| Timestamp profile stub | Implemented mock/local profile and token validation | `specs/core/trusted-timestamp-profile-v1.md`, `src/klein/timestamping/`, `tests/fixtures/timestamp/` | Not trusted timestamp proof |
| Attestation profile stub | Implemented none/mock profile and statement validation | `specs/core/attestation-profile-v1.md`, `src/klein/attestation/`, `tests/fixtures/attestation/` | Not hardware attestation proof |
| Trusted timestamp proof | Future work | `docs/ROADMAP.md`, `docs/TARGET_V1_TEST_PLAN.md` | Not current alpha |
| Hardware attestation proof | Future work | `docs/ROADMAP.md`, `docs/CLAIMS_LEDGER.md` | Not current alpha |
| Physical execution proof | Long-horizon work under threat model | `docs/CLAIMS_LEDGER.md`, `docs/CURRENT_ALPHA.md` | Not current alpha |

## Appendix A: Key Files

Core specs:

- `specs/core/kcp-core-v1.md`
- `specs/core/hail-v1.md`
- `specs/core/hail-digest-chain-v1.md`
- `specs/core/run-manifest-v1.md`
- `specs/core/trust-policy-v1.md`
- `specs/core/backend-identity-registry-v1.md`
- `specs/core/backend-capability-declaration-v1.md`
- `specs/core/run-bundle-v1.md`
- `specs/core/independent-verifier-v1.md`
- `specs/core/trusted-timestamp-profile-v1.md`
- `specs/core/attestation-profile-v1.md`
- `specs/core/runbook-v1.md`
- `specs/core/execution-trace-v1.md`
- `specs/core/ecrp-v1.md`
- `specs/core/observation-v1.md`
- `specs/core/hil-readiness-v1.md`
- `specs/core/recorded-device-run-v1.md`
- `specs/core/conformance-levels-v1.md`

Artifact and profile specs:

- `specs/artifacts/klein-project-v1.md`
- `specs/artifacts/klein-container-v1.md`
- `specs/artifacts/simgb-v1.md`
- `specs/artifacts/rimgb-v1.md`
- `specs/profiles/dmf/dmf-ewod-v1.md`
- `specs/profiles/dmf/dmf-backend-adapter-v1.md`
- `specs/profiles/dmf/opendrop-ewod-adapter-v1.md`
- `specs/profiles/dmf/opendrop-transport-planning-v1.md`

Schemas and catalogs:

- `schemas/`
- `schemas/profiles/dmf/`
- `specs/catalogs/conformance_levels.v1.json`
- `src/klein/catalogs/conformance_levels.v1.json`

Docs:

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/CURRENT_ALPHA.md`
- `docs/QUICKSTART.md`
- `docs/VALIDATION_MATRIX.md`
- `docs/VERIFY_A_BUNDLE.md`
- `docs/DMF_PROFILE.md`
- `docs/ADAPTERS.md`
- `docs/CLAIMS_LEDGER.md`
- `docs/TARGET_V1_TEST_PLAN.md`
- `docs/ROADMAP.md`

Fixtures and verifiers:

- `tests/vectors/v1/`
- `tests/fixtures/cross_language/fixtures.json`
- `tests/fixtures/run_bundle/`
- `tests/fixtures/recorded_run/`
- `verifiers/README.md`
- `verifiers/rust/README.md`
- `verifiers/rust/`

Adapter modules:

- `src/klein/backends/dmf/`
- `src/klein/backends/dmf/opendrop/`
- `src/klein/tools/dmf_backend.py`
- `src/klein/tools/opendrop_backend.py`

## Appendix B: Reproducible Commands

```bash
python -m pip install -e .[dev,crypto]
python -m compileall -q src tests
python -m pytest -q
ruff check src/klein/hail src/klein/profiles src/klein/tools src/klein/conformance src/klein/crypto src/klein/verifier src/klein/bundle src/klein/artifacts src/klein/execution src/klein/hil src/klein/recording src/klein/backends tests/test_hail_core.py tests/test_schema_parity.py
klein-conform --suite tests/vectors/v1 --check-suite-integrity
klein-conform --suite tests/vectors/v1 --backend full_simulator --json
klein-conform --suite tests/vectors/v1 --category negative --backend full_simulator --json
klein-regen-v1-goldens --suite tests/vectors/v1 --backend full_simulator --check
klein-conformance-levels validate-catalog
klein-verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
klein-recorded-run validate tests/fixtures/recorded_run/opendrop_dry_run_recorded_run
klein-opendrop-backend validate-config tests/fixtures/backends/dmf/opendrop/opendrop_dry_run_config.json
klein-opendrop-backend validate-transport tests/fixtures/backends/dmf/opendrop/opendrop_transport_none.json
cargo test --manifest-path verifiers/rust/Cargo.toml
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-fixtures tests/fixtures/cross_language/fixtures.json
cargo run --manifest-path verifiers/rust/Cargo.toml -- verify-bundle tests/fixtures/run_bundle/valid_signed_run_with_capabilities.kcprun
```

## Appendix C: Glossary

- **Artifact**: A portable input object, such as `.klein` Project v1 or `.kleinc` Container v1.
- **Runbook**: A planned execution record derived from an artifact.
- **Trace**: A record of issued/applied steps, statuses, and failures.
- **HAIL**: Hash-Addressed Intermediate Log, KCP's canonical evidence log.
- **Run Manifest**: A signed statement over lifecycle-bound run evidence.
- **Trust Policy**: A local policy authorizing keys or registry authorities for backend/profile
  scopes.
- **Backend Registry**: A registry of backend identities and signing keys.
- **Backend Capabilities**: A signed declaration of supported profiles, modes, substrates, and
  conformance levels.
- **Conformance Level**: A machine-readable claim id with dependencies, required artifacts, checks,
  evidence, and forbidden claims.
- **Run Bundle**: A portable `.kcprun` package containing run evidence and trust material.
- **Recorded Device Run**: An archive format for `.kcprun` plus raw logs, observations, HIL snapshots,
  and backend metadata.
- **HIL Readiness**: Interface contract/status readiness for future hardware-in-the-loop backends.
- **Adapter Skeleton**: A dry-run/config-only backend boundary that translates runbook steps to
  backend command shapes without hardware IO.
- **Observation**: A structured snapshot aligned with runbook and trace evidence; simulator-backed in
  current alpha.
- **Attestation**: Future evidence about the integrity or identity of a hardware/software execution
  environment.
- **Physical Proof**: A future claim that physical execution occurred under a defined threat model,
  requiring evidence beyond current alpha.

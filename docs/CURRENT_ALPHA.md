# Current Alpha Claims

This page is the human-readable summary of `docs/CLAIMS_LEDGER.md`. The ledger remains the detailed
source for individual claim IDs and evidence references.

## Current Implemented Claims

KCP currently verifies evidence artifacts and declared evidence bindings. It can validate artifacts,
build runbooks, compare traces, validate HAIL, sign manifests with local test keys, package `.kcprun`
bundles, and verify those bundles through Python and Rust verifier paths.

The alpha stack is useful because it makes evidence claims inspectable and repeatable. It does not
turn simulator evidence into physical proof.

## Current Simulator And Profile Claims

The DMF/EWOD profile alpha validates payloads against declared capability and topology constraints.
The full simulator can execute the authoritative v1 vector suite and produce HAIL evidence.

Current alpha includes one simulator-only ECRP recovery-success path and simulator-backed
Observation v1 snapshots. These are claims about simulator evidence and profile validation, not
claims about wet-lab droplet motion.

## Current Verifier Claims

The Python independent verifier and Rust verifier slice can check portable `.kcprun` bundles and
cross-language fixtures. Current verification covers bundle integrity, HAIL canonicalization,
lifecycle evidence, HAIL chain digests, manifest signatures, trust policy, backend identity
registry, signed registry provenance, backend capabilities, and conformance level references.
It also validates Trusted Timestamp Profile v1 stub artifacts: mock/local timestamp profiles and
tokens bound to target hashes.
It validates Attestation Profile v1 stub artifacts: none/mock attestation profiles and statements
bound to subjects, backend ids, or hashes.

Current verifiers do not verify physical execution, hardware observations, trusted timestamps, or
hardware attestation.

## Current Adapter Claims

HIL Readiness v1, Recorded Device Run v1, Generic DMF Backend Adapter v1, and OpenDrop/EWOD Adapter
Skeleton v1 exist as interface, archive, and dry-run/config-only layers.

The OpenDrop/EWOD adapter validates OpenDrop-style config/status/command intents, maps channels to
electrodes, generates dry-run intents, emits raw mock logs and mock observations, and can generate a
mock recorded-run package.

OpenDrop/EWOD adapter skeleton means: this is where an OpenDrop-style backend would plug in. It does
not mean KCP controls OpenDrop hardware.

OpenDrop Transport Planning v1 exists as a current-alpha planning boundary. It validates disabled
transport configs, rejects hardware IO/endpoints in strict alpha mode, and serializes command streams
for dry-run artifacts only. It does not perform serial writes or claim OpenDrop hardware support.
The current-alpha JSON Schemas enforce the same no-hardware policy: hardware IO must be `false`,
adapter endpoints and baud rates must be `null` or absent, and serialized commands must not be marked
as hardware-IO allowed.

KCP does not copy or vendor GaudiLabs/OpenDrop firmware or controller code. Future OpenDrop hardware
integration requires explicit license compatibility review before copying or deriving from
GPL-licensed code.

## Explicit Non-Claims

Current alpha does not claim:

- hardware support;
- HIL execution;
- physical truth proof;
- real sensor proof or sensor attestation;
- trusted timestamp proof or external timestamp authority verification;
- hardware attestation proof, hardware identity proof, or TPM/TEE verification;
- real OpenDrop control;
- OpenDrop serial transport or hardware IO;
- certified or production conformance.

## Target V1 Claims

`TARGET_V1` tracks work required before stronger public protocol claims are defensible:

- trusted timestamp authority validation beyond the current mock/local profile stub;
- real hardware attestation validation beyond the current none/mock profile stub;
- real backend adapter planning;
- hardware source and sensor semantics;
- signed hardware/backend capability workflows beyond local fixtures;
- recorded hardware run validation once hardware semantics are explicit.

## Long-Horizon Claims

`LONG_HORIZON` preserves the TCP/IP-for-matter ambition:

- independent hardware-backed implementations;
- substrate-neutral execution evidence across heterogeneous media;
- physical proof under an explicit threat model;
- attested hardware-backed evidence;
- recovery that actually repairs or replans under sensed substrate divergence.

The alpha is not the endpoint. It is the evidence and verification foundation needed to make those
claims precise later.

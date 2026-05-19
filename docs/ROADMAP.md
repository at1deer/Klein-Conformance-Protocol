# Roadmap

KCP is moving toward substrate-neutral conformance for physical execution under uncertainty. The
roadmap keeps current alpha claims precise while preserving the long-term TCP/IP-for-matter goal.

## Completed / Current Alpha

- Core evidence stack: artifacts, runbooks, traces, HAIL, canonicalization, lifecycle binding, and
  HAIL chain digests.
- Trust/identity stack: Run Manifest v1, Trust Policy v1, Backend Identity Registry v1, signed
  registry provenance, and Backend Capability Declaration v1.
- Bundle/verifier stack: `.kcprun` Run Bundle v1, Python independent verifier, and Rust verifier
  slice.
- DMF/EWOD profile alpha: capability/topology-driven payload validation and simulator execution.
- Artifact/runbook/trace stack: schema-backed artifact validation and planning/execution records.
- ECRP contract and simulated recovery: policy-bounded recovery evidence plus one simulator-only
  success path.
- Observation semantics: simulator-backed Observation v1 snapshots aligned with trace/runbook
  evidence.
- HIL readiness: contract/status/interface checks without hardware execution.
- Recorded Device Run format: mock/dry-run recorded-run archives wrapping `.kcprun` bundles.
- Generic/OpenDrop dry-run adapter skeletons: adapter boundaries, command translation, mock logs,
  mock observations, and recorded-run package generation.
- OpenDrop transport planning: disabled transport configs, deterministic command streams, and strict
  hardware IO/endpoint rejection without OpenDrop SDK, firmware, GPL code, or device IO.
- Trusted Timestamp Profile Stub v1: mock/local timestamp profile and token validation, target-hash
  binding checks, and status vocabulary without trusted timestamp proof.
- Attestation Profile Stub v1: none/mock attestation profile and statement validation,
  subject/backend binding checks, and status vocabulary without hardware attestation proof.
- Public-alpha documentation and whitepaper synthesis in `docs/WHITEPAPER.md`.
- Public demo package and website copy under `examples/public-alpha/` and `docs/site/`.

## Next

- Alpha release checklist and release tag.
- External timestamp authority / RFC 3161-like validation beyond the mock/local profile stub.
- Real hardware attestation verification beyond the none/mock profile stub.
- Real backend adapter planning beyond the disabled OpenDrop transport scaffold.

## Future

- Real OpenDrop transport with explicit hardware access gate and license review.
- Hardware sensor/source semantics.
- First hardware run.
- Hardware-backed evidence under an explicit threat model.
- Attested hardware execution and timestamped evidence.
- Broader substrate profile implementations beyond DMF/EWOD.

Hardware-dependent items are blocked by hardware access, safety policy, sensor semantics, timestamp
semantics, attestation semantics, and a published threat model. They should not be claimed by the
current alpha.

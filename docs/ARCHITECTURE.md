# KCP Architecture

KCP separates substrate-specific execution from evidence, packaging, trust, and verification. The
current alpha is broad enough to show the full shape of the stack, while still keeping hardware
claims out of scope until the missing measurement and attestation machinery exists.

## Evidence Stack

```text
.klein/.kleinc
    -> Runbook
    -> Execution Trace
    -> HAIL
    -> Run Manifest
    -> .kcprun Bundle
    -> Independent Verifier
```

`.klein` Project v1 and `.kleinc` Container v1 are portable input artifacts. They describe the
declared work and profile payloads.

Runbook v1 is the planned execution record derived from an artifact. It is intentionally separate
from what was actually issued or observed.

Execution Trace v1 records issued/applied steps and failures. It gives a structured comparison point
for runbook evidence, recovery evidence, and observations.

HAIL v1 is the canonical evidence log. Current alpha validates lifecycle events, hashes HAIL
canonical bytes, and computes a terminal HAIL chain digest.

Run Manifest v1 signs lifecycle-bound evidence. Run Bundle v1 packages artifacts, HAIL, manifests,
trust policies, registries, capabilities, and verifier material into `.kcprun`.

Independent verifiers consume `.kcprun` evidence without running the simulator or conformance
harness.

## Trust Stack

```text
Backend Key
    -> Backend Identity Registry
    -> Signed Registry Provenance
    -> Trust Policy
    -> Signed Backend Capabilities
    -> Verified Run Claim
```

Backend keys are test/local signing keys for alpha evidence. They are not hardware roots of trust.

Backend Identity Registry v1 declares backend identities and signing keys. Signed registry
provenance lets a local trust policy authorize a registry authority.

Trust Policy v1 decides which keys or registry authorities are authorized for a backend/profile
scope. Backend Capability Declaration v1 states what a backend claims to support.

The verifier combines these layers to decide whether a signed run claim is authorized. This stack
provides mock/local timestamp and none/mock attestation stub boundaries, but it does not provide
trusted timestamp proof, hardware attestation proof, TPM/TEE verification, or global PKI in current
alpha.

## DMF Profile Stack

```text
DMF Payload
    -> DMF Frames
    -> Runbook Steps
    -> Backend Adapter Commands
    -> Trace / Observation / Raw Log
```

The DMF/EWOD profile defines payload kinds, frame formats, topology constraints, voltage/frequency
limits, and validation failures.

The simulator converts DMF payloads into frames and executes them against a virtual substrate. The
runbook/trace split keeps planned operations separate from issued operations.

Generic DMF and OpenDrop/EWOD dry-run adapters translate runbook steps into backend command shapes,
raw mock device logs, simulator/mock observations, and Recorded Device Run packages. They do not
connect to hardware.

## Boundary Stack

```text
Simulator
    -> Mock HIL
    -> HIL-ready Adapter
    -> Future Physical Backend
    -> Future Attestation
```

The simulator is the current executable backend for authoritative v1 conformance vectors.

Mock HIL and HIL Readiness v1 define the interface shape for future hardware-in-the-loop backends.
They validate contracts, statuses, emergency-stop semantics, and operation shapes without claiming
hardware execution.

HIL-ready adapters are dry-run/config-only skeletons today. They demonstrate where backend-specific
translation, logs, observations, and recorded-run packaging belong.

Future physical backends need real transport, hardware source semantics, sensor models, trusted
timestamps, attestation, and a threat model before KCP can claim physical proof.

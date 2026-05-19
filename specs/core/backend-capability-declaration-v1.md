# Backend Capability Declaration v1

Backend Capability Declaration v1 is a signed backend claim about supported Klein protocol and profile capabilities.

It bridges backend identity/trust into profile capability semantics. It is not hardware attestation, certified hardware capability, trusted time, or proof of physical execution.

## Format

```json
{
  "capability_declaration_version": "klein.backend_capability_declaration.v1",
  "payload": {
    "declaration_id": "klein-full-simulator-dmf-v1-capabilities",
    "backend_id": "full_simulator",
    "backend_version": "1.0.0a0",
    "issued_at": null,
    "not_before": null,
    "not_after": null,
    "supported_profiles": [
      {
        "profile_id": "dmf",
        "profile_versions": ["v1"],
        "profile_capability_set": "klein.profile.dmf.ewod.alpha"
      }
    ],
    "supported_conformance_levels": [
      "KCP-Core-HAIL-v1",
      "KCP-Core-Canonical-v1",
      "KCP-Core-Chain-v1",
      "KCP-Core-Signed-Conformance-v1",
      "KCP-Core-Bundled-Verification-v1",
      "KCP-Profile-DMF-Payload-v1",
      "KCP-Profile-DMF-Simulator-v1"
    ],
    "supported_execution_modes": ["HARD", "ENVELOPE", "DIAGNOSTIC"],
    "supported_hail_features": {
      "hail_v1": true,
      "run_start": true,
      "run_end": true,
      "hail_chain_v1": true,
      "preclose_digest": true
    },
    "supported_evidence_features": {
      "run_manifest_v1": true,
      "trust_policy_v1": true,
      "backend_identity_registry_v1": true,
      "signed_backend_registry": true,
      "run_bundle_v1": true,
      "independent_verifier_v1": true
    },
    "hil": {
      "hil_readiness": false,
      "hil_contract_hash": null,
      "hil_levels_supported": [],
      "hardware_execution_supported": false,
      "hardware_attestation_supported": false
    },
    "profile_capabilities": {},
    "substrates": [],
    "limitations": [
      "Reference simulator only.",
      "No hardware attestation.",
      "No trusted timestamp.",
      "No physical sensor proof."
    ]
  },
  "signatures": [
    {
      "signature_algorithm": "Ed25519",
      "key_id": "klein-test-backend-001",
      "public_key_encoding": "base64.raw.ed25519",
      "public_key": "<base64>",
      "signature_encoding": "base64.raw.ed25519",
      "signature": "<base64>"
    }
  ]
}
```

The signature preimage is RFC 8785/JCS canonical bytes of `declaration["payload"]`. Raw JSON text and the `signatures` array are not signed.

## Semantics

- A capability declaration is a backend claim.
- It can be signed by a backend key declared in Backend Identity Registry v1.
- Trust Policy v1 decides whether that backend signing key is locally trusted.
- Bundle/independent verifiers can check the declaration against manifest/RUN_START scope.
- `limitations` are required for alpha declarations so simulator-only boundaries remain explicit.
- `supported_conformance_levels` must reference ids in `specs/catalogs/conformance_levels.v1.json`.
- Unknown, future, unsupported target, and missing-dependency level claims are invalid by default.
- Declarations claiming `KCP-Profile-DMF-Payload-v1` or `KCP-Profile-DMF-Simulator-v1` must include
  `profile_capabilities.dmf` that validates against the DMF/EWOD profile rules.
- Declarations claiming `KCP-Profile-DMF-Simulator-v1` must include at least one substrate
  fingerprint binding.
- `payload.hil` is optional. When present, it declares HIL Readiness v1 interface claims only.
- `hil_readiness: true` or any `hil_levels_supported` entry requires a `hil_contract_hash`.
- `hardware_execution_supported` and `hardware_attestation_supported` must remain `false` in
  current alpha declarations.
- `KCP-Profile-DMF-HIL-L1` and hardware-attested levels cannot be declared supported in current
  alpha.

## Scope Checks

A verifier may check:

- `backend_id` and `backend_version`
- `profile_id` and `profile_version`
- execution mode
- substrate fingerprint, when supplied
- DMF capability internal consistency

If the bundle omits a capability declaration, alpha verification remains valid unless strict capability mode is requested.

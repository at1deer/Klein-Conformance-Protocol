# Conformance Levels Matrix v1

The KCP Conformance Levels Matrix v1 is the normative table of claims in
`specs/catalogs/conformance_levels.v1.json`.

The matrix separates:

- `CURRENT_ALPHA`: implemented or partially implemented repository-backed capabilities.
- `TARGET_V1`: planned protocol requirements that are not current supported claims.
- `LONG_HORIZON`: future physical assurance and recovery goals.

Capability declarations may claim `implemented` or `partial` levels. They must not claim `future`
levels, and must not claim `target` levels unless a verifier explicitly enables target-claim mode.

The catalog is a claim-control mechanism, not hardware evidence. A level can require artifacts,
checks, tools, specs, tests, and fixtures, but no catalog entry by itself proves physical execution.

Required dependency closure is enforced. If `KCP-Core-Signed-Conformance-v1` is claimed, its core
dependencies must also be claimed or inferable by a verifier. The alpha verifier treats missing
declared dependencies as failures for signed backend capability declarations.

# Klein Core v1

Klein Core v1 is the substrate-neutral conformance layer for physical execution under uncertainty.

Core defines artifact boundaries, HAIL event semantics, canonical JSONL comparison, execution
modes, conformance result semantics, and recovery evidence rules. Core does not define DMF
electrode behavior, sensing hardware, fluid physics, or profile-specific recovery strategies.

## Normative Core Surface

- `.klein` project graph artifacts
- `.kleinc` compiled container artifacts
- SImgB static substrate state references
- RImgB runtime state evidence in HAIL
- HAIL v1 event validation
- HARD, ENVELOPE, and DIAGNOSTIC execution modes
- positive and negative conformance result rules

## Non-Claims

Klein Core does not guarantee that a physical substrate succeeds. It requires explicit declarations,
bounded attempts, canonical evidence, and honest failure reporting.

The reference simulator currently implements bounded ECRP attempt evidence and explicit failure
when recovery does not occur. In the current alpha, `ecrp_max_attempts` is a bound and the engine
emits at most one attempt for a single failed frame; it does not run a closed-loop retry cycle. It
does not implement full closed-loop physical recovery.

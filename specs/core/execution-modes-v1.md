# Execution Modes v1

## HARD

Canonical exactness is required. No invisible adaptation is allowed. Failure must be explicit.

## ENVELOPE

Divergence is allowed only within declared profile tolerances. Comparison should report the
tolerance dimension and margin used.

The alpha harness implements minimal envelope comparison for event count, event kind, and
declared tick tolerance. Numeric field-level envelope comparison remains future work.

## DIAGNOSTIC

Exploratory execution is allowed. Output is nonconformant unless later promoted by explicit
validation against a HARD or ENVELOPE contract.

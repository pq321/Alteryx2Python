# Join Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- `Left` and `Right` input anchors
- `Join`, `Left`, and `Right` output anchors
- inner join using configured Left and Right key fields
- unjoined left and right rows emitted on their respective anchors
- observed SelectConfiguration output projection
- default output names strip configured `Left_` / `Right_` prefixes

Deferred semantics:

- join-by-record-position
- multi-key edge cases beyond observed config shape
- full Select tool type conversion inside Join projection

Certification notes:

- The observed inner-join and output projection shape can participate in workflow-level golden-output certification.
- This does not certify every Join mode, multi-key edge case, or Alteryx warning/error behavior.

## Contract

Inputs:

- `Left`: pandas DataFrame
- `Right`: pandas DataFrame

Outputs:

- `Join`: joined rows after configured projection
- `Left`: unjoined left rows
- `Right`: unjoined right rows

Assertions:

- `Join`, `Left`, and `Right` anchors are emitted
- each output is a pandas DataFrame
- `Left` and `Right` unjoined output row counts do not exceed their corresponding input row counts
- parser-provided expected output schema is enforced when strict mode is enabled

Evidence status:

- runtime contract evidence is emitted on `NodeResult.contract_evidence`
- official workflow certification exists for the observed Join config in the Basic Combine workflow

# Union Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- one or more input anchors
- one output anchor named `Output`
- `ByName` mode
- output columns are the union of input columns in first-seen order
- missing cells are represented as Python `None`

Deferred semantics:

- positional union mode
- explicit output order configuration
- full warning/error handling for mismatched schemas
- Alteryx metadata and type propagation

## Contract

Inputs:

- one or more input anchors containing pandas DataFrames

Outputs:

- `Output`: by-name concatenation of all inputs

Assertions:

- `Output` anchor is emitted
- output is a pandas DataFrame
- output columns equal the first-seen by-name union of input columns ordered by routed input anchor name
- output row count equals the sum of all input row counts

Evidence status:

- runtime contract evidence is emitted on `NodeResult.contract_evidence`
- current evidence is integration-level and branch-level, not standalone official Union certification

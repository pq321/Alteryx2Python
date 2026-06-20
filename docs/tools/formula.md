# Formula Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- sequential formula evaluation against the current row state
- create new columns
- update existing columns in place
- static string and numeric literals
- field references
- arithmetic operators used by the official Formula sample
- `IF ... THEN ... ELSE ... ENDIF`
- `Titlecase`
- `ROUND`
- explicit failure for unsupported expression functions

Deferred semantics:

- complete Alteryx expression language coverage
- full Alteryx type and size coercion
- date/time functions
- multi-row or cross-row formula behavior
- golden-output certification against official examples

## Contract

Inputs:

- `Input`: pandas DataFrame

Outputs:

- `Output`: input columns plus enabled formula fields, with existing fields updated in place

Assertions:

- `Output` anchor is emitted
- output is a pandas DataFrame
- output preserves row count
- output columns preserve input columns and append newly created enabled formula fields
- parser-provided expected output schema is enforced when strict mode is enabled

Evidence status:

- runtime contract evidence is emitted on `NodeResult.contract_evidence`
- current evidence is integration-level and branch-level, not standalone official Formula certification

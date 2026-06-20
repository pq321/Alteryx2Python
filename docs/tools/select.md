# Select Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- include fields
- exclude fields marked `selected=False`
- `*Unknown` passthrough for fields not explicitly listed in the Select config
- reorder output columns
- rename columns
- explicit type conversion for a limited supported set
- row count preservation
- row order preservation
- explicit failure for missing fields, duplicate output names, and unsupported dtypes

Deferred semantics:

- field size changes
- field description metadata
- duplicate output name behavior beyond hard failure
- exact Alteryx behavior for complex dynamic/unknown-field metadata changes
- broader Alteryx type system coverage

Certification notes:

- The observed include/exclude/rename/reorder/type-conversion subset can participate in workflow-level golden-output certification.
- This does not certify the complete Alteryx type system or dynamic metadata behavior.

## Contract

Inputs:

- `Input`: pandas DataFrame

Outputs:

- `Output`: selected columns in configured order, after rename and supported dtype conversion

Assertions:

- `Output` anchor is emitted
- output is a pandas DataFrame
- output column order equals selected explicit fields plus `*Unknown` passthrough fields
- output row count equals `Input` row count
- parser-provided expected output schema is enforced when strict mode is enabled

Evidence status:

- runtime contract evidence is emitted on `NodeResult.contract_evidence`
- official workflow certification exists for observed Select configs in the Basic Combine workflow

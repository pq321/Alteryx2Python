# Select Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- include fields
- exclude-by-omission behavior through explicit selected field list
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
- broader Alteryx type system coverage
- golden-output certification against official examples

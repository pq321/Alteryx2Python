# Record ID Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- add a configured record ID column
- start from positive or negative configured values
- increment by one per row
- place the new field as first column (`Position=0`) or last column (`Position=1`)
- supported integer output dtypes: `Int16`, `Int32`, `Int64`

Deferred semantics:

- grouped record ID reset behavior
- unsigned and non-integer variants if exposed by workflows
- metadata field size handling beyond dtype selection
- golden-output certification against official examples

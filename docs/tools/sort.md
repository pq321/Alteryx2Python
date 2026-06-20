# Sort Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- one input anchor named `Input`
- one output anchor named `Output`
- one or more configured sort fields from `SortInfo/Field`
- ascending and descending order
- stable row ordering through pandas `mergesort`
- execution trace with input and output schema

Deferred semantics:

- locale-specific collation
- dictionary sort order details for mixed strings/numbers
- Alteryx warning and error text parity

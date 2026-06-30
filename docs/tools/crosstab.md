# CrossTab Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- one input anchor named `Input`
- one output anchor named `Output`
- grouping by configured group fields
- header field values become output columns
- data field values populate pivoted cells
- `First` aggregation for duplicate group/header pairs
- row and header order based on first appearance in the input

Deferred semantics:

- aggregation methods other than `First`
- field-size and separator behavior
- complete Alteryx metadata/type propagation
- certification against golden Alteryx output

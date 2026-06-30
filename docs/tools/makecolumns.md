# MakeColumns

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Input: `Input`
- Output: `Output`

Implemented semantics:

- reshapes consecutive rows into repeated numbered field columns
- supports configured `NumColumns`
- supports per-group reshaping via `GroupFields`

Deferred semantics:

- exact horizontal versus vertical ordering parity for complex layouts
- full metadata/type propagation across generated columns

# AppendFields

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Targets: `Targets`
- Source: `Source`
- Output: `Output`

Implemented semantics:

- Cartesian append of every target row with every source row
- duplicate source column names are prefixed with `Source_`
- `CartesianMode=Error` rejects many-to-many appends

Deferred semantics:

- full SelectConfiguration field projection
- exact Alteryx warning behavior for Cartesian limits

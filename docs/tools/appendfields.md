# AppendFields

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Targets: `Targets`
- Source: `Source`
- Output: `Output`

Implemented semantics:

- Cartesian append of every target row with every source row
- embedded Select configuration resolves `Target_` and `Source_` field identities separately from output names
- unrenamed fields retain their original names where available, and collisions receive the input's prefix after selection and ordering
- explicit renames, selected fields, `*Unknown` and configured field order apply in both Python phases
- `CartesianMode=Error` rejects many-to-many appends

Deferred semantics:

- exact Alteryx warning behavior for Cartesian limits

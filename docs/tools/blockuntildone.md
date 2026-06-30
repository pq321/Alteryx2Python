# Block Until Done Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- require an `Input` anchor
- copy the input DataFrame to `Output`, `Output2`, and `Output3`
- rely on runtime graph dependencies to preserve downstream ordering
- record input and output schemas in the runtime trace

Deferred semantics:

- exact Alteryx scheduling guarantees for side-effectful downstream tools
- partial-output streaming behavior
- interaction with disabled containers and detours

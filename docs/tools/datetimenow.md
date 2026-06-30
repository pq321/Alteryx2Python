# DateTimeNow

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Output: `Output`

Implemented semantics:

- emits a one-row `DateTimeNow` field
- supports `yyyy-MM-dd`, `yyyy-MM-dd HH:mm:ss`, and `MM/dd/yyyy`
- accepts `config["now"]` as a deterministic test/runtime override

Deferred semantics:

- locale-specific language formatting beyond current sample coverage

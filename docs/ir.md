# IR Notes

The canonical intermediate representation is the contract between parsing, validation, runtime execution, and generation.

Current initial models:

- `WorkflowIR`
- `NodeIR`
- `EdgeIR`
- `AnchorIR`

Current validators cover:

- unique node IDs
- edge reference integrity
- anchor reference integrity
- DAG acyclic validation

The IR layer is intentionally introduced before broader parser/generator work so XML does not become directly coupled to Python generation.

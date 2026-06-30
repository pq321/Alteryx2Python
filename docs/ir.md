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

## Contracts And Evidence

The project now separates three related concepts:

- `WorkflowIR`: source-derived workflow structure from Alteryx XML
- `ToolContract`: expected anchors, schema changes, and invariants derived from tool type, normalized config, and input schemas
- `ContractEvidence`: observed runtime results and assertion outcomes produced after a node executes

`NodeIR.expected_input_schema` and `NodeIR.expected_output_schema` remain source/parser metadata fields. They should not become a dumping ground for every runtime assertion.

The preferred boundary is:

- parser stores source metadata in `WorkflowIR` and `NodeIR`
- runtime derives or applies contracts immediately after each tool executes
- `NodeResult.contract_evidence` stores assertion results for the executed node

This keeps parsed workflow structure stable while allowing contract validation to evolve tool by tool.

## Compact Workflow View

`alteryx2python.compact.build_compact_workflow` derives an AI-facing JSON view from `WorkflowIR`.

This compact view is not a replacement for `WorkflowIR`. It is a topology-preserving projection for planning and review:

- all nodes are retained
- all edges are retained
- input/output anchors are retained
- incoming/outgoing node links are retained
- graph roots, leaves, and topological order are included
- raw XML, GUI layout, annotation shell data, and verbose metadata are omitted

The compact view should be used when the goal is to understand workflow logic without spending tokens on Alteryx canvas/UI scaffolding.

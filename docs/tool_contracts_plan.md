# Tool Contract Documentation Plan

## Why This Exists

The existing documentation treats workflow certification mostly as evidence that a target node or final output matches an Alteryx oracle. That remains useful, but it is not the strongest model for this project.

The stronger model is that every executable Alteryx tool instance has a deterministic contract:

- what inputs it accepts
- what output anchors it emits
- what schema each output anchor should have
- what row/data-shape invariants should hold
- what type coercions or semantic changes are expected
- what evidence proves the Python implementation matched the Alteryx behavior

This shifts the documentation direction from final-output comparison to node-level, assertion-driven certification.

## Existing Documentation Direction

Current docs already contain the right foundation:

- `SPEC.md` says one Alteryx tool maps to one Python node by default, tool boundaries must be preserved, and final-output equality alone is insufficient.
- `docs/architecture.md` describes parser -> IR -> runtime -> comparison -> certification.
- `docs/ir.md` defines IR as the contract between parsing, validation, runtime, and generation.
- `docs/testing_strategy.md` describes tool tests, runtime tests, integration tests, and golden-output evidence.
- `docs/certification.md` defines certification evidence, but it is currently workflow-slice and target-output oriented.
- `docs/tools/*.md` describe implemented/deferred semantics per tool, but they do not yet define machine-checkable contracts.

The new direction does not replace those docs. It makes the implicit node-level contract explicit.

## Proposed Documentation Model

### 1. Constitution Layer

File: `SPEC.md`

Add a dedicated section for tool contracts and intermediate evidence.

The section should establish:

- every executable node may have a `ToolContract`
- final-output equality is only one certification layer
- node-level contract evidence is preferred when available
- unsupported or unknown node behavior must produce an explicit waiver, not silence
- optimized/generated code is not certified unless it preserves the same node contracts

This should be a principle-level change, not implementation detail.

### 2. Architecture Layer

File: `docs/architecture.md`

Update the architecture diagram and package responsibilities to include:

- a contract/assertion layer between `tools`, `runtime`, and `comparison`
- node execution evidence captured per node and per output anchor
- contract validation as part of runtime/certification, not only post-run comparison

The architecture should make this flow explicit:

```text
WorkflowIR
  -> Tool semantics
  -> Node execution result
  -> ToolContract validation
  -> NodeEvidence
  -> Workflow certification report
```
### 3. IR Layer

File: `docs/ir.md`

Expand the IR docs to separate three concepts:

- parsed source metadata from Alteryx XML
- expected schema/contracts inferred from tool configuration
- observed runtime evidence produced by Python execution

Do not overload `NodeIR` with every assertion detail. The docs should clarify whether contracts belong directly in IR, in a sidecar structure keyed by node ID, or in runtime evidence. The likely direction is:

- `WorkflowIR` remains source structure
- `ToolContract` is derived from `WorkflowIR + tool registry semantics`
- `NodeEvidence` is produced by runtime execution

### 4. Certification Layer

File: `docs/certification.md`

Change certification from mostly target-output evidence to layered evidence:

1. parser evidence
2. tool contract evidence
3. node-level schema evidence
4. node-level data-shape evidence
5. anchor-routing evidence
6. target/final-output golden evidence

Certification reports should be able to say:

- node `7` passed schema assertions but has no Alteryx oracle sample
- node `23` passed output bytes comparison
- node `36` has branch-level evidence only
- node `X` has an explicit unsupported-contract waiver

### 5. Testing Strategy Layer

File: `docs/testing_strategy.md`

Add a new test category:

- contract derivation tests: given normalized tool config and input schema, expected output contracts are produced
- contract validation tests: given actual dataframe outputs, assertions pass/fail with useful diagnostics
- workflow evidence tests: a graph execution emits per-node evidence

These tests should sit between isolated tool semantic tests and full workflow golden-output tests.

### 6. Tool Documentation Layer

Files: `docs/tools/*.md`

Add a standard contract section to each tool doc.

Suggested template:

```text
## Contract

Inputs:
- anchor name
- accepted schema constraints

Outputs:
- anchor name
- expected schema transformation
- expected row-count behavior
- expected ordering behavior

Assertions:
- schema assertions
- dtype assertions
- row/data-shape assertions
- semantic assertions

Evidence status:
- unit evidence
- integration evidence
- Alteryx oracle evidence
- known waivers
```

Example for `Select`:

- output columns match selected/reordered/renamed fields
- row count is preserved
- row order is preserved
- supported dtype conversions match configured target types
- missing configured fields fail explicitly

Example for `Join`:

- `Join`, `Left`, and `Right` anchors are emitted
- join keys exist on both inputs
- join output schema follows projection rules
- unjoined rows are routed to the correct anchors
- row count relationship is explainable by join cardinality

### 7. CLI/User Guide Layer

Files: `README.md`, `docs/cli.md`

Do not lead with contracts yet. First update the technical docs. After the contract system exists, update CLI docs to describe commands such as:

```text
inspect-contract
run --emit-evidence
certify --node-contracts
compare-node
```

Until implementation exists, CLI docs should only mention this as roadmap.

### 8. Backlog Layer

File: `checklist.md`

Add a new milestone before expanding many more tools:

```text
M15 - Node-Level Tool Contracts And Evidence
```

Recommended tasks:

- define `ToolContract`, `AnchorContract`, and assertion result structures
- derive contracts for `Select`, `Filter`, `Formula`, `Join`, and `Union`
- validate contracts during runtime execution
- emit per-node evidence in workflow results
- add readable certification report output
- update tool docs with contract sections

## Proposed Contract Vocabulary

Use a small vocabulary first.

Schema assertions:

- `columns_equal`
- `column_exists`
- `column_absent`
- `column_order_equals`
- `dtype_equals`
- `nullable_equals`

Shape assertions:

- `row_count_equals_input`
- `row_count_less_than_or_equal_input`
- `row_count_equals_sum_of_anchors`
- `unique_key`
- `sorted_by`

Semantic assertions:

- `values_not_null`
- `values_in_set`
- `expression_matches`
- `join_keys_preserved`
- `formula_output_matches`

Routing assertions:

- `anchor_emitted`
- `anchor_not_emitted`
- `edge_receives_expected_anchor`
- `multi_anchor_partition_complete`

## Suggested JSON Shape

This is a documentation target, not a committed implementation contract yet.

```json
{
  "node_id": "7",
  "tool_type": "Select",
  "input_anchors": {
    "Input": {
      "schema": {
        "CustomerID": "String",
        "Amount": "Float64"
      }
    }
  },
  "output_anchors": {
    "Output": {
      "schema": {
        "CustomerID": "String",
        "AmountUSD": "Float64"
      },
      "assertions": [
        {"type": "column_order_equals", "columns": ["CustomerID", "AmountUSD"]},
        {"type": "row_count_equals_input", "input_anchor": "Input"},
        {"type": "dtype_equals", "column": "AmountUSD", "expected": "Float64"}
      ]
    }
  },
  "waivers": []
}
```

## Rollout Order

Recommended order for the next documentation pass:

1. Update `docs/certification.md` because it is where the conceptual shift matters most.
2. Update `docs/architecture.md` so readers understand where contracts fit.
3. Update `docs/ir.md` to define the boundary between IR, derived contracts, and evidence.
4. Update `docs/testing_strategy.md` to add the new test class.
5. Add contract sections to `docs/tools/select.md`, `docs/tools/filter.md`, `docs/tools/formula.md`, `docs/tools/join.md`, and `docs/tools/union.md`.
6. Update `checklist.md` with `M15`.
7. Update `SPEC.md` after the terminology stabilizes across the docs.
8. Update `README.md` last, once the project has an implementation-facing story.

## Key Decision

The project should not treat every contract as an Alteryx oracle comparison. Some contracts are inferred from tool semantics and can be validated without running Alteryx. Oracle-backed evidence is stronger, but inferred contract evidence is still valuable because it localizes errors to a specific tool and anchor.

This gives the migration pipeline a better debugging loop:

```text
final output mismatch
  -> find first failing node contract
  -> inspect tool config and generated Python parameters
  -> fix one tool implementation or parser normalization
  -> rerun node-level evidence
```

# Architecture

This project follows a structure-first migration path:

1. Parse Alteryx workflow artifacts into a canonical IR.
2. Validate graph, anchors, configs, and support status.
3. Execute or generate Python from IR through registered tool semantics.
4. Validate node-level tool contracts against each intermediate output.
5. Compare target/final outputs and schemas against golden evidence.
6. Produce certification-oriented reports.

Key package responsibilities:

- `alteryx2python.ir`: canonical workflow model and validators.
- `alteryx2python.parser`: source parsing into IR.
- `alteryx2python.compact`: topology-preserving compact workflow JSON for AI analysis and planning.
- `alteryx2python.tools`: tool semantics and metadata registry.
- `alteryx2python.runtime`: execution context, trace, and node execution.
- `alteryx2python.contracts`: node-level schema, anchor, and shape assertions.
- `alteryx2python.expressions`: controlled expression parsing/evaluation.
- `alteryx2python.comparison`: schema/value comparison and reporting.
- `alteryx2python.generator`: code generation from validated IR.
- `alteryx2python.optimizer`: intentionally disabled for baseline migration.

The runtime evidence flow is:

```text
WorkflowIR
  -> registered tool semantics
  -> node outputs by anchor
  -> ToolContract / inferred assertion validation
  -> ContractEvidence on NodeResult
  -> workflow certification report
```

Contracts are intentionally checked at Alteryx tool boundaries. That keeps the generated Python traceable to the original workflow and makes mismatches local: a failing final output can be traced back to the first failing node contract.

For token-efficient analysis, the compact workflow view projects `WorkflowIR` into a smaller JSON shape that preserves nodes, anchors, edges, roots, leaves, and topological order while dropping raw XML and Alteryx GUI shell fields.

Real workflow intake starts with the inventory in `docs/workflow_inventory.md`. That document is the authoritative summary of sample-workflow structure, plugin distribution, and external dependency surface for parser and integration planning.

Current parser normalization coverage maps these plugin families to dedicated parsers:

- `AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect` -> `Select`
- `AlteryxBasePluginsGui.CrossTab.CrossTab` -> `CrossTab`
- `AlteryxBasePluginsGui.DbFileInput.DbFileInput` -> `DbFileInput`
- `AlteryxBasePluginsGui.DynamicRename.DynamicRename` -> `DynamicRename`
- `AlteryxBasePluginsGui.Formula.Formula` -> `Formula`
- `AlteryxBasePluginsGui.Filter.Filter` -> `Filter`
- `AlteryxBasePluginsGui.JSONParse.JSONParse` -> `JSONParse`
- `AlteryxBasePluginsGui.RecordID.RecordID` -> `RecordID`
- `AlteryxBasePluginsGui.Join.Join` -> `Join`
- `AlteryxBasePluginsGui.Union.Union` -> `Union`
- `AlteryxBasePluginsGui.Transpose.Transpose` -> `Transpose`

Interface, action, and connector plugins remain parsed but deferred until their semantics are explicitly implemented.

Runtime graph execution now supports validated `WorkflowIR` graphs through `run_workflow_graph`:

- topological ordering from `WorkflowIR.edges`
- anchor-aware routing between node outputs and downstream inputs
- multi-output anchors such as Filter `True` and `False`
- in-memory intermediate outputs keyed by node ID
- per-node contract evidence for emitted anchors and supported tool invariants
- fail-fast unsupported tool errors with context errors recorded
- runtime traces in node execution order
- optional target-node execution through `target_node_ids`
- automatic ancestor selection for targeted execution
- explicit warnings for skipped frontier nodes downstream of the selected subgraph

Current runtime boundaries:

- cycle detection stops execution before running nodes
- unknown edge node references fail validation in the executor
- unsupported tools stop execution rather than being skipped
- contract failures stop execution with an assertion error instead of allowing bad intermediate data to flow downstream
- targeted subgraph execution only runs ancestors of requested target nodes; non-frontier skipped nodes are reported in `WorkflowGraphResult.skipped_node_ids` but do not emit warnings

The first real workflow execution slice parses `examples/sample_workflows/MIFID II.yxwz` and executes nodes `18 -> 21 -> 22 -> 23 -> 24`:

- `DbFileInput`
- `Select`
- `JSONParse`
- `Formula`
- `Filter`

The original node `18` points at an unavailable local Excel file, so the integration test swaps that node's normalized file config to a repo-safe CSV fixture with the same `DownloadData` input surface. The downstream `CrossTab` node `25` remains unsupported and is recorded as the skipped frontier after the Filter `True` anchor.

The first M8 reshape slice extends that same real workflow to target node `36`, covering:

- `CrossTab`
- `DynamicRename`
- `RecordID`
- `Transpose`
- `Join`
- `Union`
- the first post-union `Formula`

Node `32` is redirected to a repo-safe `mapping.csv` fixture for this slice. Output nodes and the later final formatting/output branch remain deferred.

M9 adds a narrow `DbFileOutput` implementation:

- CSV output is supported for `FileFormat=0`.
- Excel output from the observed MIFID output node is explicitly deferred.
- The first golden comparison fixture is `tests/fixtures/real_workflows/mifid_target36_expected.csv`, compared against the target node `36` branch output.

M11 generation emits executable baseline Python that rebuilds `WorkflowIR` and delegates execution to `run_workflow_graph`. Generated code preserves original node IDs and configs instead of inlining optimized pandas transformations.

M12 governance is captured in `docs/governance.md` and `alteryx2python.unsupported`. Future tool additions should update parser normalization, runtime semantics, docs, isolated tests, integration tests, and comparison evidence in that order.

# Technical Design: Phase 2 IR Graph Optimizer

## Module Boundary

Create `alteryx2python/generator/ir_optimizer.py` exposing:

```python
@dataclass
class OptimizationResult:
    workflow: WorkflowIR
    folded_parameters: list[dict]          # lifted 1-row TextInput/Action parameters
    reusable_macros: dict[str, MacroSubgraphSpec]
    loop_macros: dict[str, LoopMacroSpec]
    provenance: dict[str, dict]            # original node_id -> status/target_node_id/reason

def optimize_workflow_ir(workflow: WorkflowIR, *, parameter_specs: list[dict] = (), parameter_bindings: list[dict] = ()) -> OptimizationResult: ...
```

## Pass Ordering & Fixed-Point Iteration

Run passes in a deterministic order (repeating lightweight local simplifications up to a bounded fixed point of 4 rounds):

1. **`classify_and_inline_macros`**:
   - Inspect all `Macro_*` nodes. Count invocations per resolved macro path + structural configuration signature.
   - `BatchMacro` / `IterativeMacro` → build `LoopMacroSpec` (preserving child `WorkflowIR`, iteration input/output anchors, max iterations, and macro questions).
   - Standard Macro with 1 call (or <= 3 trivial tabular nodes) and no macro-local events → inline into parent graph, stripping `MacroBoundaryInput` / `MacroOutput` passthroughs.
   - Standard Macro with >= 2 calls → build 1 `MacroSubgraphSpec` (recursively optimized!) and keep lightweight `MacroCall` nodes in parent graph.
2. **`fold_single_row_parameter_tables`**:
   - Match `TextInput` (1 row, unique column names, no incoming edges, sole outgoing edge to `AppendFields.Source` where `AppendFields` has `Targets` connected and no name collision).
   - Lift each column to a scalar parameter (reusing existing Question parameter name if an Action already targets `r[1]/c[k]`, otherwise creating a config parameter from the `TextInput` column name and default value).
   - Rewrite downstream `FieldReference(col)` in `Formula` / `Filter` (prior to shadowing by any later assignment of `col`) to `ParameterExpression(param_name)` and rewire `AppendFields` consumers directly to `AppendFields.Targets` source!
3. **`prune_noop_and_dead_branches`**:
   - Bypass identity `Select`, `BrowseV2`, `TextBox`, `HtmlBox`, and static `ToolContainer` nodes.
   - Walk backward from observable sinks (`DbFileOutput`, `PortfolioComposerRender`, `Email`, `RunCommand`, `Message`, connected `ControlContainer`, `MacroOutput`, or terminal outputs when workflow has no file sinks in pure-transform fixtures) to drop unreachable dead branches.
4. **`fuse_select_chains` & `prune_dead_columns`**:
   - Compose `Select_A -> Select_B` when `Select_A` has a single consumer and both are in the same container/control guard scope.
   - When downstream consumers have closed column sets (no `*Unknown` wildcard or dynamic field access), mark unreferenced columns unselected upstream.
5. **`fuse_formulas_and_filters`**:
   - Merge `Formula_A -> Formula_B` (single consumer, identical container guard) by concatenating `formula_fields` in order.
   - Merge `Filter_A --(True/False)--> Filter_B` (single consumer on one anchor, other anchor unused, identical container guard) by combining ASTs (`BinaryExpression("AND", cond_a_or_negated, cond_b)`).

## Safety Invariants

- Never fuse across `BlockUntilDone` barriers, different `ToolContainer` / `ControlContainer` guard conditions, or side-effecting `Message` / `RunCommand` nodes.
- Never fold `AppendFields` if `TextInput` has != 1 row or overlapping case-insensitive column names with known `Targets` columns unless `SelectConfiguration` explicitly renames/drops conflicts.

# PRD: Phase 2 IR Graph Optimizer and Redundancy Elimination

## Goal

Eliminate Alteryx-authored structural bloat in `WorkflowIR` before Phase 2 code generation while preserving 100% end-to-end boundary semantics.

## Ordering & Dependencies

- **Child 1 of `11-21-native-modular-phase2`** (no upstream child dependencies; executes first).

## Requirements

1. **No-Op & Dead-Branch Pruning**
   - Remove `BrowseV2`, `TextBox`, `HtmlBox`, disabled/empty `ToolContainer` wrappers, and identity `Select` nodes (selecting `*Unknown` with no drops, renames, reorders, or dtype changes).
   - Prune unconnected non-sink branches while preserving all observable sinks (`DbFileOutput`, `PortfolioComposerRender`, `Email`, `RunCommand`, `Message`, connected `ControlContainer`, `MacroOutput`).
2. **General 1-Row Parameter Table Folding**
   - Detect private 1-row `TextInput` nodes feeding `AppendFields` (`Source` anchor) into a data stream (`Targets` anchor) in **general dynamic mode** (not limited to `specialized` mode), lifting each cell into a named workflow parameter (preserving Analytic App Action bindings if present) and replacing the `AppendFields` Cartesian join with direct parameter references in downstream `Formula`/`Filter` expressions.
3. **`Select` Consolidation & Dead-Column Pruning**
   - Algebraically compose adjacent single-consumer `Select -> Select` chains (combining column selection, rename chains `a -> b -> c`, and final declared type conversions).
   - Compute backward liveness of columns from all sinks and `Unknown`-consuming boundaries; drop provably dead columns early instead of copying them across intermediate steps.
4. **Consecutive `Formula` and `Filter` Fusion**
   - Merge consecutive single-consumer `Formula -> Formula` nodes into a single ordered `Formula` node while respecting intra-formula dependencies and variable scopes.
   - Merge consecutive single-consumer `Filter -> Filter` nodes (where the unconsumed anchor has zero downstream edges) into a single conjunctive/negated boolean expression (`(cond1) AND (cond2)` or `(!(cond1)) AND (cond2)`).
5. **Macro Classification & De-bloating**
   - Classify macros into three lowering representations:
     - **Inline Standard Macro**: single-invocation (or trivial wrapper) Standard Macros without macro-local events inline directly into the host IR *before* `Select`/`Formula` fusion so macro boundary projections fold away.
     - **Reusable Standard Macro**: Standard Macros invoked 2+ times with compatible structural shape remain represented as a single reusable `MacroSubgraphSpec` with per-call parameter bindings instead of duplicating nodes N times.
     - **Iterative / Batch Macro**: `BatchMacro` and `IterativeMacro` definitions parse into explicit `LoopMacroSpec` structures (`kind="batch" | "iterative"`, control/iteration anchors, max-iteration bound) ready for native loop emission in Child 2.
6. **Provenance Mapping**
   - Emit an optimization provenance map linking every original `node_id` to either its surviving/merged IR node or an explicit elimination reason (`passthrough_select`, `folded_parameter_table`, `fused_formula`, `inlined_macro`, etc.).

## Acceptance Criteria

- Chained `Select -> Select`, `Formula -> Formula`, single-branch `Filter -> Filter`, 1-row `TextInput + AppendFields`, and single-use wrapper macros reduce IR node count deterministically while producing identical sink outputs when executed on the canonical Phase 1 runtime.
- Multi-invocation Standard Macros produce 1 shared `MacroSubgraphSpec` with N call sites rather than N duplicated node copies.
- Every original `node_id` is accounted for in the provenance map.
- Unit and differential tests for `ir_optimizer.py` pass with >=85% module coverage.

## Out of Scope

- Emitting `.py` or `config.toml` files (owned by `11-21-phase2-native-package`).

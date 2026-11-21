# Implementation Plan: Phase 2 IR Graph Optimizer

## Checklist

1. Read `.trellis/spec/backend/readable-python.md` and inspect `alteryx2python/ir/models.py`, `alteryx2python/generator/parameters.py`, and `alteryx2python/generator/macro_sources.py`.
2. Implement `MacroSubgraphSpec`, `LoopMacroSpec`, and `classify_and_inline_macros` in `alteryx2python/generator/ir_optimizer.py`.
3. Implement `fold_single_row_parameter_tables` handling both static 1-row `TextInput` cells and Analytic App `Action`-bound `TextInput` cells.
4. Implement `prune_noop_and_dead_branches`, `fuse_select_chains`, and conservative `prune_dead_columns`.
5. Implement `fuse_formulas_and_filters` preserving expression evaluation order and container guards.
6. Add comprehensive unit and Phase 1 differential tests in `tests/test_generator/test_ir_optimizer.py` covering:
   - Chained `Select -> Select -> Select` with renames, drops, and dtype overrides;
   - Split `Formula` chains where Formula 2 references a column computed in Formula 1;
   - Chained `Filter` on `True` and `False` branches, plus non-fusion when both anchors are consumed;
   - 7-question Analytic App `TextInput + AppendFields` folding in dynamic mode;
   - Single-use Standard Macro inlining vs. 2-call Standard Macro deduplication vs. Batch/Iterative Macro spec extraction;
   - Container guard boundaries (`ControlContainer` / disabled `ToolContainer`) preventing unsafe cross-guard fusion.

## Validation Commands

```powershell
.venv/Scripts/python.exe -m pytest tests/test_generator/test_ir_optimizer.py -q
.venv/Scripts/python.exe -m pytest tests/test_generator -q
```

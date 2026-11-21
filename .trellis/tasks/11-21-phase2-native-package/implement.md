# Implementation Plan: Config-Decoupled Native Python Package Emitter

## Prerequisite Check

- Confirm `11-21-phase2-ir-optimizer` is implemented and passing tests before starting this task.

## Checklist

1. Implement `alteryx2python/generator/config_extractor.py` to build `ConfigSpec`, serialize commented `config.toml`, and export multi-row `TextInput` tables to `references/*.csv`.
2. Implement `alteryx2python/generator/vectorized_lowering.py` for AST-to-Pandas Series lowering (`np.where` / `np.select`, `.str`, `.dt`, vectorized arithmetic/boolean predicates) with clean scalar fallback only for non-vectorizable functions.
3. Implement semantic stage segmentation and `pipeline.py` / `cli.py` / `io_utils.py` / `macros/*.py` emitters in `alteryx2python/generator/package_compiler.py`.
4. Implement Option A data-driven semantic refinement (`RefinementRule` detection & targeted re-emission) when Phase 1 reference outputs reveal case-insensitive key, string-truncation, or CSV-formatting differences.
5. Add comprehensive unit and standalone subprocess execution tests in `tests/test_generator/test_package_compiler.py`:
   - 7-question Analytic App: verify `pipeline.py` has ~40-60 lines of clean Pandas, zero hardcoded file paths or answers, and runs identically for `defaults`, `alternate`, and `empty` configs without recompiling `.py` files;
   - Multi-row `TextInput` extracted to `references/*.csv`;
   - Reusable Standard Macro, Batch Macro, and Iterative Macro emitted under `macros/`;
   - Workflow `Events` (Before/After/OnError logging, email draft, allowlisted command) isolated in `cli.py` / `io_utils.py`;
   - Option A refinement triggered on mixed-case Join keys and narrow `String(4)` truncation, while staying absent on clean datasets.

## Validation Commands

```powershell
.venv/Scripts/python.exe -m pytest tests/test_generator/test_package_compiler.py -q
.venv/Scripts/python.exe -m pytest tests/test_generator -q
```

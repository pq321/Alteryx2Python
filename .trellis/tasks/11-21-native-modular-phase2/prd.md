# Config-Decoupled, IR-Optimized Native Python Package Compiler for Phase 2

## Goal and User Value

Transform Phase 1 → Phase 2 compilation from single-file, input-injected, Alteryx-flavored script generation into a general-purpose, rule- and template-driven compiler that emits **self-contained, config-decoupled, idiomatic modular Python packages**.

Once Phase 1 (`WorkflowIR` + canonical runtime) has proven equivalence against Alteryx Designer, Phase 2 is free to eliminate Alteryx graph redundancies and runtime scaffolding, preserving business logic and end-to-end observable outputs while producing code that engineers can maintain directly as native Python without any dependency on Alteryx or `alteryx2python`.

## Confirmed Repository Facts

- Currently, `parity/migration.py` rewrites `DbFileInput` paths in staged XML (`inputs/1/...`), and `parity/delivery.py` invokes `ReadablePythonGenerator().generate(..., parameter_mode="specialized")`, baking one-off test paths and Analytic App answers directly into `phase_two.py`.
- `alteryx2python/generator/native_io.py` embeds file paths, CSV/Excel format options, and full `TextInput` literal `pd.DataFrame(...)` payloads directly inside Python stage functions.
- `alteryx2python/generator/native_fields.py` and `native_tabular.py` propagate `df.attrs["alteryx_schema"]`, `declare_field`, `bounded_text`, and row-wise `[... for row in df.to_dict("records")]` comprehensions across intermediate steps.
- `alteryx2python/generator/business_source.py` inlines linear node chains into monolithic `prepare_*` functions while `source_linker.py` copies ~150+ lines of internal runtime helpers (`_csv_input_*`, `_dbfileoutput_*`, `_appendfields_*`) into every generated file.
- `alteryx2python/parity/delivery.py` currently enforces 1-to-1 intermediate node checkpoint comparisons (`_compare_checkpoints`), preventing Phase 2 from merging redundant `Select` / `Formula` / `Filter` chains or wrapper macros.
- `pyproject.toml` targets `python >= 3.11` (`tomllib` and `json` are available in the Python standard library; `PyYAML` is not an installed dependency).

## Core Requirements

1. **General-Purpose Rule & Template Compilation (No Sample-Specific Repair)**
   - Define explicit target architecture templates and deterministic node/stage lowering rules; compile any supported workflow according to its optimized operator graph without LLM inference or workflow-specific patches.
2. **Strict Separation of Code vs. Config/Inputs**
   - Externalize all I/O paths and format settings (`DbFileInput`, `DbFileOutput`, `DynamicInput`, `Render`, `Email`), Analytic App `Questions` ("ask user question"), `User.*` workflow constants, lifecycle `Events` settings, and `TextInput` data (1-row parameter tables → `[parameters]`; multi-row lookup tables → `references/*.csv`) into structured external configuration (`config.toml`, with `.json` override support).
   - Keep static business logic literals (e.g., fixed filter constants `[status] = "posted"`, arithmetic multipliers, aggregation keys) directly inside Python functions for code readability.
   - Never bake staged parity snapshot paths (`inputs/1/...`) or single-run Analytic App answers into delivered Python source code; pass run-specific inputs via external config files.
3. **Adaptive Self-Contained Native Python Package Deliverable**
   - Emit a zero-framework, standalone Python package directory (`config.toml`, `pipeline.py`, `cli.py`, `io_utils.py`, plus on-demand `macros/` and `references/`, alongside `manifest.json` and `workflow.ir.json`).
   - Generated packages must execute with Python stdlib + `pandas` (and standard format libraries such as `openpyxl` when Excel I/O is used), with zero imports of `alteryx2python` or `alteryx_runtime` and zero `alteryx_schema` metadata scaffolding.
4. **IR Redundancy Elimination Before Code Emission**
   - Optimize `WorkflowIR` prior to lowering: fold consecutive `Select` nodes, drop identity `Select`/`Browse`/empty container wrappers, prune dead intermediate columns, fuse consecutive single-consumer `Formula` and single-branch `Filter` nodes, fold 1-row parameter `TextInput + AppendFields` patterns in general dynamic mode, inline trivial single-use Standard Macros, deduplicate multi-call Standard Macros into shared functions, and lower Batch/Iterative Macros into native loop modules.
5. **Option A Data-Driven Native Semantics**
   - Default to clean, vectorized idiomatic Pandas (`df.assign`, `np.where`, `.loc`, `merge`, `groupby().agg()`, `.str`, `.dt`).
   - Automatically inject explicit quirk-preserving Pandas operations (e.g., `.str.casefold()` for case-insensitive keys, `.str.slice(0, width)` for intentional truncation, integral float formatting) only when static rules require it or when Phase 1 vs. Phase 2 differential verification detects data-level divergence.
6. **Multi-Case Boundary Differential Equivalence Gate**
   - Replace intermediate node-by-node checkpoint locking with end-to-end boundary equivalence between Phase 1 and Phase 2 across default inputs, perturbed config parameters, and empty-input (0-row) cases—verifying all sink outputs, exit codes, error/warning contracts, and lifecycle event logs.

## Task Map (Independently Verifiable Child Tasks)

1. **`11-21-phase2-ir-optimizer`**: Phase 2 IR graph normalization, operator fusion (`Select`/`Formula`/`Filter`), dead-column pruning, parameter-table folding, and macro classification/deduplication.
2. **`11-21-phase2-native-package`** *(depends on `11-21-phase2-ir-optimizer`)*: Config extraction (`config.toml` + `references/*.csv`), semantic stage segmentation, vectorized Pandas templates, Option A quirk specialization, and adaptive package emission (`pipeline.py`, `cli.py`, `io_utils.py`, `macros/`).
3. **`11-21-phase2-boundary-delivery`** *(depends on `11-21-phase2-native-package`)*: Multi-case boundary differential verifier and integration into `parity/migration.py`, `parity/delivery.py`, `parity/presentation.py`, `cli.py`, `webapp`, and comparison benchmarks (`compare.py`, `compare_app.py`).

## Cross-Child Acceptance Criteria

- Changing input file paths, Analytic App answers, or `User.*` variables requires **zero edits to `.py` files**—running `python -m <package> --config <case_config>` produces exact Phase 1 equivalent outputs.
- Redundant chained `Select` nodes, split `Formula` chains, single-row `TextInput + AppendFields` parameter plumbing, and single-use wrapper macros are measurably eliminated in generated `pipeline.py`.
- Generated `pipeline.py` contains pure `pd.DataFrame -> pd.DataFrame` stage functions and a concise `run_pipeline(config)` orchestrator with zero `alteryx_schema`, `declare_field`, or internal `_dbfileoutput_*` / `_csv_input_*` helper dumps.
- Multi-case differential verification (default case + perturbed parameters + 0-row input) passes on both transaction and 7-question Analytic App benchmarks as well as workflow event/macro fixtures, and the project test suite passes with >=80% coverage.

## Out of Scope

- Modifying Phase 0 (Alteryx Designer) ↔ Phase 1 (`XmlWorkflowParser` + `PythonGenerator` + canonical runtime) node-level parity semantics.
- Supporting proprietary third-party connectors, cloud credentials, or unlicensed binary models already classified as external prerequisites.

# PRD: Config-Decoupled Native Python Package Emitter & Vectorized Templates

## Goal

Compile optimized `WorkflowIR` graphs into self-contained, config-decoupled, idiomatic Python packages where all external inputs/parameters live in `config.toml` (and `references/*.csv`), static business constants remain readable in Python code, and transformation stages are modular pure functions using native vectorized Pandas.

## Ordering & Dependencies

- **Child 2 of `11-21-native-modular-phase2`**.
- **Prerequisite**: Complete `11-21-phase2-ir-optimizer` first so `package_compiler` consumes `OptimizationResult`.

## Requirements

1. **Structured Config & Reference Extraction**
   - Emit `config.toml` (readable by Python >=3.11 stdlib `tomllib`, with `.json` override support in `io_utils.load_config`) containing `[inputs.*]`, `[outputs.*]`, `[parameters]` (Analytic App questions, `User.*` constants, folded 1-row parameter tables), and optional `[references]` / `[events]`.
   - Extract multi-row `TextInput` lookup tables to `references/<name>.csv` instead of embedding DataFrame literals inside `.py` files.
   - Keep static business literals (comparison constants, multipliers, group/sort keys) inside Python transformation functions.
2. **Adaptive Self-Contained Package Layout**
   - Always emit `config.toml`, `pipeline.py`, `cli.py`, `__main__.py`, `__init__.py`, `io_utils.py`, `manifest.json`, and `workflow.ir.json`.
   - Emit `macros/<name>.py` **only** when multi-invocation Standard Macros or Batch/Iterative Macros exist.
   - Emit `references/<name>.csv` **only** when multi-row `TextInput` tables exist.
3. **Native Modular `pipeline.py` & Idiomatic Vectorized Templates**
   - Group pure dataflow operations into semantic stage functions (`pd.DataFrame -> pd.DataFrame`, accepting explicit keyword parameters from `config["parameters"]`).
   - Emit `run_pipeline(config: dict)` orchestrating input reads, pure stage calls, and output writes.
   - Lower common `Formula` and `Filter` expressions to vectorized Pandas/NumPy (`df.assign`, `np.where`, `np.select`, `.str`, `.dt`, `.isna()`, `.fillna()`), eliminating intermediate `alteryx_schema` / `declare_field` / `bounded_text` scaffolding.
4. **Option A Data-Driven Semantic Specialization**
   - Default to clean idiomatic Pandas (`merge`, `.eq()`, standard dtypes, `to_csv`).
   - When given optional Phase 1 reference outputs (or during verification-guided compilation), automatically refine specific operations that diverge on real data (e.g., `.str.casefold()` join/filter keys, `.str.slice(0, width)` string truncation, integral-float CSV formatting) without polluting unaffected operations.

## Acceptance Criteria

- Generated packages contain **zero** imports of `alteryx2python` or `alteryx_runtime`, **zero** `alteryx_schema` / `declare_field` references, and **zero** hardcoded input/output paths or Analytic App answer literals inside `pipeline.py`.
- Supplying a different `--config alternate.json` or `--set region=EMEA` produces exact Phase 1 outputs for alternate inputs/parameters **without regenerating Python code**.
- Simple workflows without reusable macros or multi-row `TextInput` tables do not create empty `macros/` or `references/` directories.
- All supported components (Questions/Actions, `User.*` variables, `Events`, reusable/Batch/Iterative macros, `Python Tool`, Reporting/Email profiles) lower cleanly into their designated package layers.

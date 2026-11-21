# Technical Design: Native Modular Phase 2 Compiler

## 1. Architecture Overview

Phase 1 (`WorkflowIR` + canonical runtime) remains the exact node-for-node oracle against Alteryx Designer. Phase 2 becomes a genuine optimizing compiler from `WorkflowIR` to an idiomatic, config-decoupled Python package:

```text
WorkflowIR (or verified Phase 1 script via read_phase_one)
   │
   ▼
[Layer 1: IR Graph Optimizer] (alteryx2python/generator/ir_optimizer.py)
   ├── Macro Classifier: inline 1-call standard macros; extract N-call / Batch / Iterative macros
   ├── Parameter Table Folder: 1-row TextInput + AppendFields -> named workflow parameters
   ├── Operator Fusion: Select->Select composition, Formula->Formula fusion, single-branch Filter fusion
   └── Dead-Branch & Dead-Column Pruner: remove Browse/passthrough Select/unused columns & disconnected anchors
   │
   ▼
[Layer 2: Config & Reference Extractor] (alteryx2python/generator/config_extractor.py)
   ├── Externalize I/O endpoints & format options -> [inputs.*], [outputs.*]
   ├── Externalize Questions/Actions, User.* constants & folded 1-row tables -> [parameters]
   ├── Externalize multi-row TextInput tables -> references/<name>.csv + [references.*]
   └── Externalize lifecycle Events (Before/After/Error email, command, JSONL log) -> [events]
   │
   ▼
[Layer 3: Semantic Stage & Vectorized Emitter] (alteryx2python/generator/package_compiler.py)
   ├── Partition pure dataflow into semantic stages (clean, enrich/join, compute/filter, aggregate/sort)
   ├── Lower expressions to vectorized Pandas/NumPy ASTs (scalar helper fallback only when stateful/non-vectorizable)
   ├── Option A Quirk Refinement: clean Pandas by default; targeted .str.casefold() / .str.slice() only on detected divergence
   └── Emit adaptive self-contained package directory (<pkg>/pipeline.py, config.toml, cli.py, io_utils.py, [macros/], [references/])
   │
   ▼
[Layer 4: Multi-Case Boundary Differential Verifier] (alteryx2python/parity/boundary_delivery.py)
   └── Execute Phase 1 vs. standalone Phase 2 subprocess across default, parameter-perturbed, and 0-row cases
```

## 2. Target Deliverable Package Contract

Every compiled workflow produces an adaptive directory `<package_name>/`:

- **`config.toml`** *(stdlib `tomllib` in Python >=3.11; `io_utils.load_config` accepts both `.toml` and `.json`)*:
  - `[inputs.<alias>]`: `path`, `format`, `delimiter`, `encoding`, `sheet`, `skip_rows`, `max_rows`, `has_header`
  - `[outputs.<alias>]`: `path`, `format`, `delimiter`, `encoding`, `sheet`, `has_header`
  - `[parameters]`: typed default values for Analytic App questions, `User.*` workflow constants, and folded 1-row parameter cells (with inline `#` comments documenting description/choices/bounds)
  - `[references]`: relative paths to `references/<name>.csv` (present only when multi-row `TextInput` nodes exist)
  - `[events]`: lifecycle hook definitions (present only when workflow events are enabled)
- **`pipeline.py`**:
  - Pure transformation functions (`def clean_trades(df: pd.DataFrame) -> pd.DataFrame`, `def build_trade_report(df: pd.DataFrame, *, region: str, ...) -> pd.DataFrame`).
  - Top-level `run_pipeline(config: dict) -> dict[str, Path]` performing only I/O reads via `io_utils`, pure stage calls, and I/O writes.
  - Zero file path literals, zero `alteryx_schema` / `declare_field`, zero runtime helper clutter.
- **`cli.py` & `__main__.py`**:
  - `argparse` interface supporting `--config <path.toml|path.json>`, `--input-dir`, `--output-dir`, `--set key=value` / `--<param-name>`, and `--interactive` (prompting Analytic App questions when requested).
  - Parameter validation (bounds, choices, required checks, ISO dates) and `with workflow_lifecycle(config):` wrapper for `Events`.
- **`io_utils.py`**:
  - Clean, concise, standalone Python helpers (`load_config`, `read_delimited`, `write_delimited`, `read_excel_sheet`, `write_excel_sheet`, `workflow_lifecycle` when events exist). Named as ordinary Python utilities without converter-internal prefixes.
- **`macros/`** *(emitted only when needed)*:
  - Reusable functions for multi-call Standard Macros (`run_<macro_name>(df, *, ...)`), `for` batch loops for `BatchMacro`, and bounded `while` convergence loops for `IterativeMacro`.
- **`references/`** *(emitted only when needed)*:
  - UTF-8 CSV files extracted from multi-row `TextInput` lookup tables.
- **`manifest.json` & `workflow.ir.json`**:
  - Provenance hashes, `config_schema`, optimization pass log (recording which source `node_id`s were fused/eliminated into which stage function and line number in `pipeline.py`), and verification status.

## 3. Option A: Data-Driven Native Semantics Refinement

To avoid polluting every string operation or join with defensive Alteryx wrappers while guaranteeing exact equivalence:

1. **Initial Lowering**: Emit clean, idiomatic Pandas (`df.merge(...)`, `df["col"].eq(val)`, standard string/numeric dtypes, standard `to_csv`).
2. **Static Intentional Contracts**: Only emit `.str.slice(0, width)` upfront if a `Formula`/`Select` string width is explicitly narrower than upstream/literal width, or explicit integer/decimal rounding when configured as a type conversion.
3. **Differential Quirk Specialization**: When reference/staged inputs are available during compilation or delivery verification, compare Phase 1 boundary outputs against Phase 2 boundary outputs. If a mismatch is traced to:
   - Case-insensitive `Join` / `Unique` / `Summarize` / `Filter` string comparison → specialize that specific operation with temporary `.str.casefold()` normalize keys.
   - CSV trailing `.0` formatting on integral floats or custom null rendering → enable clean column formatting in `io_utils.write_delimited` for that output.
   - String width truncation triggered by actual data → emit explicit `.str.slice(0, width)` on that column.
   Re-emit deterministically and re-verify until boundary outputs match 100%.

## 4. Compatibility, Migration & Rollback Strategy

- **Decoupled Delivery Flow (`parity/migration.py` & `parity/delivery.py`)**:
  - `prepare_migration` records both `original_source` and `staged_source` + `inputs.json` mapping original input nodes/files to staged snapshot paths.
  - `verify_delivery` compiles the Phase 2 package from the **un-staged workflow** in dynamic/config-driven mode (`delivery/package/`), writes `delivery/case_config.json` binding staged snapshot paths and `answers.json`, and runs standalone subprocess verification via `python -I -m <pkg> --config case_config.json`.
- **Coexistence with Existing Single-File API**:
  - Keep `ReadablePythonGenerator` operational during Child 1 & Child 2 development so existing 1,200+ unit tests remain green, then introduce `ModularPackageGenerator` (and wire `ReadablePythonGenerator.generate_package` / CLI `--output <dir>` / `delivery` / `presentation` / `webapp`) in Child 2 & Child 3 cleanly without big-bang breakage.
  - In `webapp/backend.py`, `CompileResult.python` surfaces the clean `pipeline.py` source alongside `files` (full package file map, including `config.toml`), so the browser preview immediately reflects the modular output.

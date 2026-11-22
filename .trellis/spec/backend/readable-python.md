# Readable Python Compilation Contract

- Phase Two consumes preserved WorkflowIR or a structurally recognized Phase One
  script. Never execute an input script or infer business intent from its text.
- Expressions lower from the existing expression AST. Generated execution must
  not import either project package or contain a graph/expression interpreter.
- Readability is a compiler property, never a sample-specific output repair.
  Resolve static configuration before emission; inline trivial wrappers and
  assemble stages from dependency boundaries. Do not relocate a generic runtime
  into generated support files and call it readable.
- Keep checkpoint machinery in a separate verification build from the same AST.
  Execute the delivered source as well; verification-only success is insufficient.
  Exercise changed fields, configurations and topologies through the same rules.
- Template and helper sources are versioned and hashed. Preserve node/function
  mappings and original IR in sidecars. Never overwrite maintained artifacts.
- Unknown tools, dynamic configurations, unhandled enabled events and metadata
  stubs are explicit compile blockers. A registered tool is not an implementation.
- Explicit specialized exports bind current answers before native compilation;
  record mode/answers/constant overrides. Never silently freeze dynamic inputs.
- Reusable exports expose a frame-in, frame-out `transform` and an explicit
  file adapter. File paths, App answers and any run clock are runtime values.
  Keep replay bindings outside the Python source. Split only graphs whose
  file I/O order and effects can be preserved. Record the reason when a
  migration needs a case-bound export.
- Direct Question references and event tokens use current dynamic parameters.
  Record-field precedence applies even to User/Global/Engine/Question names.
- Workflow email attachments use relocated sink bindings when applicable;
  external attachments preserve their configured paths. Never choose stale
  input files merely because a same-named current output exists elsewhere.
- Native field type/size declarations must survive conversion, including fixed
  integer storage widths, string widths and decimal width/scale.
- Python Tool explicit types bypass dtype inference and use output storage
  widths; unspecified source/description inherit input metadata. Supplied
  metadata overrides inherited values in runtime and generated code alike.
- Command/event execution is explicit and allowlisted. Verification overrides
  working directories; ordinary execution respects configured directories.
- Blocking branch scheduling and nested container membership apply in both the
  canonical runtime and generated code. Keep container owners inside macros.
- Python differential acceptance compares all outer anchors, exact values,
  dtypes, order, declared schemas and real artifacts. Native evidence is separate.
- Inventory rows remain visible when sample/configuration/dependency evidence is
  missing. Compilation probes never count as execution or native acceptance.

Regression cases: embedded macros after source deletion; nested disabled
containers; Windows command quoting; success/failure/warning events; user inputs
changed without recompilation; typed overflow/truncation; source overwrite gates.

---

## Scenario: Config-Decoupled, IR-Optimized Modular Package Compilation

### 1. Scope / Trigger
- Applies whenever compiling Phase 1 (`WorkflowIR` / `phase_one.py`) into Phase 2
  deliverable Python packages via `ModularPackageGenerator`, `cli.py readable`,
  `parity/delivery.py`, `parity/migration.py`, `parity/presentation.py`, or `webapp/backend.py`.

### 2. Signatures
- `optimize_workflow_ir(workflow, *, parameters=None, parameter_bindings=None, parameter_expressions=None) -> OptimizationResult`
- `extract_config(opt, *, original_workflow=None, delivery_profile=None, log_event_ids=()) -> ConfigSpec`
- `ModularPackageGenerator().generate(workflow, *, answers=None, constants=None, parameter_mode="dynamic", delivery_profile=None, log_event_ids=(), input_bindings=None, reference_capture=None, reference_input_dir=None, reference_overrides=None) -> PackageArtifact`
- CLI: `alteryx2python readable <source> --output <dir_or_py> [--format auto|package|single-file]`

### 3. Contracts
- **Strict Code vs. Input Decoupling**:
  - Externalize all I/O paths and format options (`[inputs.*]`, `[outputs.*]`), Analytic App `Questions`, `User.*` workflow constants, and folded 1-row `TextInput` parameter cells (`[parameters]`), multi-row `TextInput` lookup tables (`references/<key>.csv` + `[references.*]`), and lifecycle `Events` (`[[events.hooks]]`) into `config.toml` (parsed via Python >=3.11 stdlib `tomllib`; `.json` overrides also supported).
  - Keep static business logic literals (fixed filter strings/thresholds, arithmetic constants, group/sort keys) directly inside Python stage functions.
  - Never bake staged parity snapshot paths (`inputs/1/...`) or single-run Analytic App answers into delivered `.py` files; bind run-specific snapshots via an external `case_config.json`.
- **IR Redundancy Elimination**:
  - Eliminate UI no-ops (`BrowseV2`, `TextBox`, `HtmlBox`), static enabled `ToolContainer` wrappers, identity `Select` nodes, and unreachable dead branches.
  - Fold private 1-row `TextInput + AppendFields` parameter patterns into scalar parameters in general dynamic mode.
  - Algebraically compose consecutive `Select -> Select` chains (unless intermediate narrow cast/truncation would be lost), fuse consecutive single-consumer `Formula` nodes and single-branch `Filter` nodes, inline 1-call Standard Macros, deduplicate 2+-call Standard Macros into `macros/<key>.py`, and lower `BatchMacro` / `IterativeMacro` to explicit loop modules in `macros/<key>.py`.
- **Adaptive Self-Contained Package Layout**:
  - Always emit `__init__.py`, `__main__.py`, `config.toml`, `audit_utils.py`, `pipeline.py`, `cli.py`, `io_utils.py`, `manifest.json`, and `workflow.ir.json`.
  - Emit `macros/` only when reusable/loop macros exist; emit `references/` only when multi-row `TextInput` tables exist; emit `helpers.py` only when non-vectorizable functions or specialized kernels are referenced.
  - Every input read, reference load, intermediate stage (`audit.run_step`), skipped conditional branch (`audit.skip_step`), and output write emits structured step-by-step auditing via `audit_utils.py` (configurable under `[logging]` in `config.toml` and `--log-level` / `--log-format` / `--audit-log` in `cli.py`; see `logging-guidelines.md`).
- **Option A Data-Driven Semantic Specialization**:
  - Emit clean, vectorized idiomatic Pandas (`df.assign`, `np.where`, `.loc`, `merge`, `groupby().agg()`) without `alteryx_schema` / `declare_field` noise by default.
  - When `reference_capture` from Phase 1 diverges on real data, apply minimal targeted refinements in cascade order: Tier 1a `.str.slice(0, width)` -> Tier 1b `.str.casefold()` on Join/Unique -> Tier 2 exact scalar/type semantics, recording applied rules in `manifest.json["option_a_refinements"]`.
- **Record-Field Precedence Gotcha**:
  - Bare `[field_name]` AST references ALWAYS resolve to DataFrame columns `df["field_name"]`, even when an Analytic App Question shares the same name (e.g., `[region]` column vs. `region` DropDown Question). Only `ParameterExpression(name)` or explicit `[Question.*]` / `[User.*]` / `[Engine.*]` namespaces resolve to parameters.

### 4. Validation & Error Matrix
- Unknown/unavailable tool or unimplemented configuration -> `UnsupportedLowering`
- Project import (`alteryx2python*`, `alteryx_runtime*`) or interpreter (`run_workflow_graph`, `evaluate_expression`) in generated `.py` -> `UnsupportedLowering`
- Input/output file parameter changing configured file suffix -> `ValueError` at CLI/config load
- Parameter outside numeric bounds / invalid choice / malformed ISO date -> `ValueError` in `validate_parameters`
- Command outside `allowed_commands` -> `PermissionError`
- Overwriting non-empty destination directory -> `FileExistsError`

### 5. Good / Base / Bad Cases
- **Good**: 7-question Analytic App compiles once into a ~41-line `pipeline.py` + `config.toml`; `defaults`, `alternate`, and `empty` runs produce identical `pipeline.py` SHA-256 and match Phase 1 solely by swapping `--config <case>.json`.
- **Base**: Workflow with narrow `V_WString(3)` truncating `"ABCDEF" -> "ABC"` triggers Tier 1a Option A refinement, adding `.str.slice(0, 3)` while keeping vectorized Pandas.
- **Bad**: Compiling from staged XML with `parameter_mode="specialized"` so `'inputs/1/trades.csv'` and `'APAC'` are hardcoded inside `pipeline.py`.

### 6. Tests Required
- `tests/test_generator/test_ir_optimizer.py`: Select/Formula/Filter fusion, lossy truncation preservation, 1-row `TextInput + AppendFields` dynamic folding, 1-call macro inlining vs. 2-call deduplication vs. Batch/Iterative loop specs, container guard boundaries.
- `tests/test_generator/test_package_compiler.py`: 7-question single-compile multi-config execution, multi-row `TextInput` CSV extraction, `User.*` parameter override via `--set`, Option A refinement cascade, workflow logging & email events.
- `tests/test_parity_behavior/test_boundary_delivery.py`: Un-staged compilation during `resume_migration`, `case_config.json` binding, automatic `parameter_perturbation` and `empty_input` boundary differential verification.

### 7. Wrong vs. Correct

#### Wrong
```python
# Hardcoding staged snapshot paths, 1-row parameter DataFrames, and Alteryx schema scaffolding:
path = input_dir / 'inputs/1/trades.csv'
reference_data = pd.DataFrame({'suffix': pd.Series(['Reviewed'])})
declare_field(out, 'label', {'type': 'V_WString', 'size': 100})
```

#### Correct
```python
# Externalizing inputs/parameters to config.toml and keeping pipeline.py as pure native Pandas:
def compute_report_fields(df: pd.DataFrame, *, region: str, suffix: str) -> pd.DataFrame:
    out = df.copy()
    out["label"] = out["trade_id"].astype("string") + " " + suffix
    return out.loc[out["region"].eq(region).fillna(False)].copy()
```


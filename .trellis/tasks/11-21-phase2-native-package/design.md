# Technical Design: Config-Decoupled Native Python Package Emitter

## 1. Package Artifact Model

Introduce `PackageArtifact` in `alteryx2python/generator/package_compiler.py`:

```python
@dataclass
class PackageArtifact:
    files: dict[str, str | bytes]   # relative POSIX path -> UTF-8 text or bytes
    manifest: dict                  # node/stage mappings, config schema, hashes, refinements
    workflow: WorkflowIR
    entrypoint: str = "pipeline.py"

    @property
    def source(self) -> str:
        return str(self.files["pipeline.py"])

    def write(self, destination: Path) -> list[Path]: ...
```

## 2. Config Schema (`config_extractor.py`)

- **`[inputs.<slug>]`**: derived from node annotation or filename stem (`trades`, `customers`). Fields: `path`, `format` (`"csv"` | `"excel"` | `"dynamic"`), `delimiter`, `encoding`, `sheet`, `skip_rows`, `max_rows`, `has_header`. If bound to a `FileBrowse` Question, `input_param = "<question_name>"` links `[parameters]` to the input reader cleanly.
- **`[outputs.<slug>]`**: `path`, `format`, `delimiter`, `encoding`, `sheet`, `has_header`, `line_terminator`.
- **`[parameters]`**: all `Questions`, `User.*` constants, and folded 1-row `TextInput` columns with TOML comments describing label, type, bounds, and allowed choices.
- **`[references]`**: `desk_mapping = "references/desk_mapping.csv"` for multi-row `TextInput` nodes (with schema dtypes preserved in `io_utils` reader options if needed).
- **`[events]`**: structured list of `before`, `after`, `on_success`, `on_error` hooks (command, email draft/SMTP, JSONL log).

## 3. Vectorized Expression & Stage Lowering (`vectorized_lowering.py`)

- Lower `ExpressionNode` ASTs directly to Series expressions on `df`:
  - `FieldReference(col)` → `df["col"]` (or `param_name` when `ParameterExpression` / `Question.*` / `User.*`).
  - `BinaryExpression("+" | "-" | "*" | "/")` → vectorized arithmetic (`df["a"] + " " + suffix` for string concat; numeric Series ops for numbers).
  - `ConditionalExpression` → `np.where(cond, true_expr, false_expr)` (nested conditionals flatten cleanly to `np.select([c1, c2], [v1, v2], default=v_else)`!).
  - `FunctionExpression`: map common Alteryx functions (`TRIM` → `.str.strip()`, `UPPERCASE` → `.str.upper()`, `LOWERCASE` → `.str.lower()`, `CONTAINS` → `.str.contains(..., regex=False, na=False)`, `LEFT`/`SUBSTRING` → `.str.slice(...)`, `ISNULL` → `.isna()`, `ISFINITE`/`ABS`/`ROUND`, `DATETIMEFORMAT` → `pd.to_datetime(...).dt.strftime(...)`, `FILEADDPATHS` → path join Series) to native Pandas expressions; fall back to clean pure helper functions in `io_utils.py` (or `helpers.py`) only when no vectorized equivalent exists.
- **Semantic Stage Segmentation**:
  - Instead of either 1-function-per-node or 1-giant-inlined-function, segment pure transformations at semantic transitions:
    1. Input preparation (`Select` / `AutoField` / `DataCleansing` immediately following an input) → `clean_<entity>(df)`
    2. Multi-stream combination (`Join` / `Union` / `FindReplace` / `AppendFields`) → `join_<left>_<right>(...)`
    3. Business derivation & filtering (`Formula` + `Filter` block) → `build_<target>(df, *, ...)` / `filter_<target>(df, *, ...)`
    4. Aggregation & ordering (`Summarize` + `Sort` + `Sample` + `Rank` + terminal `Select`) → `summarize_<target>(df)`

## 4. Option A Refinement Pass

`ModularPackageGenerator.generate(workflow, *, reference_capture=None, ...)` accepts an optional Phase 1 capture (`node_results` / sink frames). When provided:
- Runs the generated pure `run_pipeline` in-memory/tempdir against the reference input config.
- If a sink frame/file differs from Phase 1:
  - Inspects column-level diffs (case-folding match? trailing `.0` float formatting? max-width string slice?) and adds targeted `RefinementRule` entries (`casefold_join_nodes`, `sliced_columns`, `alteryx_csv_format_outputs`), re-emitting minimal idiomatic code that resolves the exact discrepancy and recording `refinements` in `manifest.json`.

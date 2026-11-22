# Logging Guidelines

> Step-by-step auditing and workflow lifecycle logging conventions for Phase 2 packages and migration verification.

---

## Scenario: Template-Driven Step Auditing in Generated Phase 2 Packages

### 1. Scope / Trigger
- Applies to all generated Phase 2 modular Python packages (`ModularPackageGenerator`, `package_templates.py`, `config_extractor.py`, `package_compiler.py`) and explicit Alteryx After-Run workflow logging migrations (`alteryx2python/workflow_logging.py`).

### 2. Signatures
- Generated module `audit_utils.py`:
  - `create_audit_logger(config: dict | None = None, *, scope: str | None = None) -> AuditLogger`
  - `AuditLogger.start_pipeline(*, parameters: dict | None = None) -> None`
  - `AuditLogger.record_io(kind: str, key: str, tool_label: str, df: pd.DataFrame, path: Path | str | None, duration_ms: float) -> None`
  - `AuditLogger.run_step(step_name: str, tool_label: str, description: str, func, /, *args, **kwargs)` (PEP 570 positional-only prefix)
  - `AuditLogger.skip_step(step_name: str, tool_label: str, description: str, *, reason: str = "guard_condition_false") -> None`
  - `AuditLogger.finish_pipeline(*, outputs: dict | None = None) -> None`
  - `AuditLogger.fail_pipeline(error: BaseException) -> None`
- Generated CLI flags (`cli.py`):
  - `--log-level {DEBUG,INFO,WARNING,ERROR,OFF}`
  - `--log-format {text,jsonl}`
  - `--audit-log <PATH>`

### 3. Contracts
- **Standard Library Only**: Generated packages MUST use Python stdlib `logging` (`pipeline.audit.<run_id>`) with `propagate = False` and explicit `handler.close()` in `finish_pipeline()` / `fail_pipeline()` so Windows never retains open file locks.
- **Externalized `[logging]` Config**:
  - `config.toml` includes `[logging]` (`enabled = true`, `level = "INFO"`, `format = "text"`, `file = ""`).
  - Default output goes to `sys.stderr` (never `sys.stdout` and never creating files inside `--output-dir`), preserving `cli.py` stdout path output and byte/hash output directory parity checks.
  - When `file` ends with `.jsonl` (or `format = "jsonl"`), records serialize as JSON Lines with `run_id`, `step_index`, `kind`, `step`, `tool`, `summary`, `status`, `inputs`, `outputs`, `row_delta`, `columns_added`, `columns_removed`, `parameters`, `artifact`, `duration_ms`, and `timestamp`.
- **Pure Stage Functions & Collision-Free Dispatch**:
  - Business stage functions (`def <stage>(df: pd.DataFrame, ...) -> pd.DataFrame`) remain 100% pure DataFrame transforms without inline logging noise.
  - `AuditLogger.run_step` MUST keep `step_name, tool_label, description, func` before `/` (positional-only) so arbitrary workflow parameter kwargs (such as `summary=...` or `description=...`) never collide.
- **Privacy & Redaction Rules (What NOT to Log)**:
  - NEVER log raw DataFrame cell or row values (PII/business data). Log only structural metadata (`rows`, `cols`, column names, row/column deltas, artifact filenames, timing).
  - Redact any parameter key containing `password`, `secret`, `token`, `api_key`, `apikey`, or `credential` as `"***REDACTED***"`.

### 4. Validation & Error Matrix
- Unhandled exception in input/step/output -> `run_step` (if inside transform) + `fail_pipeline` emit `ERROR` audit records with `error_type` and `error`, close file handlers, and re-raise the original exception so exit status and traceback remain intact.
- `--log-level OFF` or `enabled = false` -> detaches handlers (`stderr == ""`), while `run_pipeline(config)["audit"]` still returns in-memory audit records.

### 5. Good / Base / Bad Cases
- **Good**: 7-question app logs `START -> [Step 1] INPUT trades -> [Step 2] STEP select_... -> [Step 3] STEP compute_... (3x4 -> 1x6, rows -2) -> [Step 4] OUTPUT report -> DONE` to `stderr` while keeping `pipeline.py` at ~50 lines.
- **Base**: Passing `--audit-log audit.jsonl` writes structured JSONL records to `audit.jsonl` without polluting `--output-dir`.
- **Bad**: Writing `audit.log` into `--output-dir` by default (breaks output directory parity) or passing `summary=...` as a keyword to `run_step` (collides with user Question named `summary`).

### 6. Tests Required
- `tests/test_generator/test_package_compiler.py::test_step_auditing_logs_text_jsonl_skip_redaction_and_failures`: verifies `text` stderr output, `.jsonl` persistent file records, row/column deltas, secret redaction, no cell-value leakage, `--log-level OFF`, and `FAIL` record capture on runtime error.

### 7. Wrong vs. Correct

#### Wrong
```python
# Sprinkling print() inside pure business functions or colliding with user parameter `summary`:
def compute_fields(df, *, summary):
    print(f"Input data:\n{df.head()}")  # Leaks PII to stdout and breaks CLI stdout contract!
    ...
audit.run_step("compute_fields", compute_fields, df, summary="Compute fields", summary=params["summary"])  # SyntaxError!
```

#### Correct
```python
# Keeping stage functions pure and using PEP 570 positional-only metadata in run_step:
select_df = audit.run_step(
    "compute_fields", "Formula->Filter #5,6", "Compute [label] -> Filter rows",
    compute_fields, df, summary=params["summary"],
)
```

# PRD: Template-Driven Step Auditing Logs for Phase 2 Packages

## Background & Goal
Generated Phase 2 modular Python packages must emit clear, structured, general-purpose auditing logs across all intermediate data processing steps, inputs, outputs, and conditional branches so reviewers and auditors can inspect what every stage of any migrated workflow is doing at runtime without opening Alteryx Designer or modifying generated business code.

## Requirements
1. **Universal Template-Driven Auditing**:
   - Emit a reusable, framework-free stdlib logging template (`audit_utils.py`) as part of every generated Phase 2 package, applying automatically to all workflows (`ModularPackageGenerator`).
   - Zero project (`alteryx2python` / `alteryx_runtime`) or third-party logging dependencies; rely exclusively on Python standard library `logging`, `json`, `time`, `uuid`, `datetime`, `sys`, `pathlib`, and `pandas`.
2. **Step-by-Step Coverage Across All Operations**:
   - Log pipeline start (run ID + redacted runtime parameters) and pipeline completion/failure (total steps, outputs, elapsed ms, error details).
   - Log every input table read (`read_input_table`) and reference table load (`read_reference_table`) with source Alteryx Tool ID, path, and loaded shape (`rows x cols` + columns).
   - Log every intermediate processing stage (`Select`, `Formula`, `Filter`, `Join`, `Summarize`, `Union`, `Unique`, `CrossTab`, `Transpose`, fused stages, reusable/loop macro calls, etc.) with:
     - Step index & Python stage function name
     - Provenance (`Tool #<id>` / `Tools #a,#b` + tool type chain)
     - Deterministic human-readable summary of what the step does (selected/cast columns, computed fields, filter rule, join/group keys, etc.)
     - Input vs. output DataFrame shapes (`rows x cols`), row delta (`+/-N`), added columns (`+cols`), removed columns (`-cols`), and step duration in milliseconds (`ms`).
   - Log dynamically skipped container/detour branches (`SKIP`) so conditional non-execution is auditable.
   - Log every output sink write (`write_output_table`: CSV, Excel, HTML/XLSX report, Email draft/SMTP) with written shape and artifact path.
3. **Config-Driven & CLI-Controllable Without Polluting Output Directories**:
   - Expose `[logging]` section in `config.toml` (`enabled = true`, `level = "INFO"`, `format = "text"`, `file = ""`).
   - Expose CLI flags `--log-level` (`DEBUG|INFO|WARNING|ERROR|OFF`), `--log-format` (`text|jsonl`), and `--audit-log <path>` in generated `cli.py`.
   - Default to `stderr` (`INFO`, `text`) so stdout and `--output-dir` file artifacts remain completely unpolluted for byte/hash parity checks.
   - Return structured `audit` step records in `run_pipeline(config)["audit"]`.
4. **Data Privacy & Clean Code Preservation**:
   - Never log raw DataFrame cell/row values (only structural shapes, column names, deltas, timing, and redacted parameters).
   - Keep pure transformation functions (`def <stage>(df, ...) -> pd.DataFrame`) 100% pure and free of logging boilerplate; keep `pipeline.py` concise (`<= 70` lines on the 7-question app benchmark).

## Acceptance Criteria
- Every generated Phase 2 package includes `audit_utils.py` and `[logging]` in `config.toml`.
- Running any generated package emits step-by-step audit logs to `stderr` in `text` mode by default and supports `jsonl` mode and `--audit-log <file>` persistent audit logs without recompilation.
- PEP 570 positional-only parameters prevent keyword collisions with arbitrary user parameter names (e.g., `summary`, `step_name`, `description`).
- All existing parity, boundary-delivery, CLI, webapp, and generator tests continue to pass with >= 80% repository coverage.

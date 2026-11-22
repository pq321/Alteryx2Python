# Implementation Plan: Template-Driven Step Auditing Logs for Phase 2 Packages

## Checklist
1. Add `logging: dict[str, Any]` (`enabled`, `level`, `format`, `file`) and node `source_tool_id` metadata on `[inputs.*]`, `[references.*]`, and `[outputs.*]` in `alteryx2python/generator/config_extractor.py`.
2. Add `render_audit_utils_py()` to `alteryx2python/generator/package_templates.py`, wire optional `audit` parameter into `read_input_table`, `read_reference_table`, and `write_output_table` in `render_io_utils_py()`, and add `--log-level`, `--log-format`, and `--audit-log` CLI options in `render_cli_py()`.
3. Add deterministic step audit summary synthesis (`_describe_node_audit`) and `audit.run_step(...)` / `audit.skip_step(...)` / `create_audit_logger(config)` orchestration emission in `alteryx2python/generator/package_compiler.py` (including macro module import adjustment for `audit_utils`).
4. Add unit and integration tests in `tests/test_generator/test_package_compiler.py` verifying:
   - Human-readable `text` stderr step logs across inputs, transforms (with row/column deltas & parameter collisions like `summary`), skipped branches, macros, and outputs.
   - Structured `jsonl` audit file output (`--audit-log` / `--log-format jsonl`) and `--log-level OFF` silencing.
   - Programmatic `run_pipeline(config)["audit"]` structured step records and failure auditing.
5. Update `.trellis/spec/backend/logging-guidelines.md` and `.trellis/spec/backend/readable-python.md` with the Phase 2 step auditing contract.
6. Run full test & coverage gates (`pytest` >= 80%, `compare_app`, `compare.py`, `verify-delivery`).

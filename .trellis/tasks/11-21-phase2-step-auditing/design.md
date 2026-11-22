# Design: Template-Driven Step Auditing Logs for Phase 2 Packages

## 1. Module & Config Boundaries
- **`config.toml` (`config_extractor.py`)**:
  Adds a `[logging]` table to `ConfigSpec`:
  ```toml
  [logging]
  enabled = true
  level = "INFO"
  format = "text"
  file = ""
  ```
- **`audit_utils.py` (`package_templates.py: render_audit_utils_py`)**:
  Self-contained stdlib `logging` helper defining `AuditLogger` and `create_audit_logger(config, *, scope=None)`:
  - `start_pipeline(*, parameters=None)`
  - `record_io(kind, name, tool_label, df, path, duration_ms)`
  - `run_step(step_name, tool_label, description, func, /, *args, **kwargs)` — uses PEP 570 `/` positional-only parameters so user kwargs like `summary=...` or `description=...` can never collide.
  - `skip_step(step_name, tool_label, description, *, reason="condition_false")`
  - `finish_pipeline(*, outputs=None)` / `fail_pipeline(error)`
  - Supports both human-readable `text` formatting and structured `jsonl` formatting (`--log-format jsonl` or `.jsonl` file extension on `--audit-log`), using `logging.getLogger(f"pipeline.audit.{run_id}")` with handler cleanup so repeated in-process calls do not leak handlers.
- **`io_utils.py` & `cli.py` (`package_templates.py`)**:
  - `read_input_table(config, key, *, audit=None)`, `read_reference_table(config, key, *, audit=None)`, and `write_output_table(df, config, key, *, audit=None)` time I/O and invoke `audit.record_io(...)` when `audit` is provided.
  - `cli.py` adds `--log-level`, `--log-format`, and `--audit-log` flags, merging overrides into `config["logging"]`.
- **`pipeline.py` & `macros/*.py` (`package_compiler.py`)**:
  - Stage functions remain 100% pure DataFrame transforms.
  - `_describe_op_audit(node, cfg)` deterministically synthesizes concise 1-line operation summaries from IR config (`Select`, `Formula`, `Filter`, `Summarize`, `Join`, `Union`, `Unique`, `RecordID`, `CrossTab`, `Transpose`, `RegEx`, `MacroSubgraphCall`, `MacroLoopCall`, etc.); fused stages join summaries with `" -> "` and combine `source_tool_id`s.
  - `run_pipeline(config)` creates `audit = create_audit_logger(config)`, wraps stage calls with `audit.run_step(...)`, logs skipped guarded branches via `audit.skip_step(...)`, logs unhandled errors via `audit.fail_pipeline(exc)`, and returns `"audit": audit.records`.
  - Macro subgraphs (`is_macro=True`) keep flat `MacroInput`/`MacroOutput` boundary wiring for `_adapt_macro_body_module`, while logging inner macro steps at `DEBUG` scope when invoked inside loops.

## 2. Safety & Compatibility
- Default console handler writes to `sys.stderr` (never `sys.stdout` and never creating files inside `--output-dir`), preserving `cli.py` stdout contract and `parity/delivery.py` file-hash equality.
- Sensitive parameter keys (`password`, `secret`, `token`, `api_key`) are redacted in audit records and log messages.

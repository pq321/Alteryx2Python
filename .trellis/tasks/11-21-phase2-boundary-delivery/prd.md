# PRD: Multi-Case Boundary Differential Verifier & Migration/CLI/WebApp Integration

## Goal

Wire the new config-decoupled, IR-optimized Phase 2 package compiler into migration delivery, CLI, presentation workflows, benchmarks, and the Web Editor—replacing 1-to-1 intermediate node checkpoint locking and `specialized` snapshot codegen with **multi-case boundary differential verification** driven by external configuration files.

## Ordering & Dependencies

- **Child 3 of `11-21-native-modular-phase2`**.
- **Prerequisite**: Complete `11-21-phase2-native-package` first.

## Requirements

1. **Un-Staged Compilation + Case-Config Delivery (`parity/migration.py` & `parity/delivery.py`)**
   - Record original workflow path alongside staged native workflow metadata in `prepare_migration`.
   - Compile the delivered Phase 2 package from the **original un-staged workflow** in dynamic/config-decoupled mode (never injecting `inputs/1/...` snapshot paths or one-off `answers.json` values into Python code).
   - Emit `case_config.json` (or `case_config.toml`) in the delivery directory mapping staged snapshot inputs, isolated output directory, and recorded answers for verification runs.
2. **Multi-Case Boundary Differential Verification**
   - Verify Phase 1 (`run_workflow_graph`) vs. standalone Phase 2 subprocess (`python -I -m <pkg> --config ...`) across:
     1. Recorded / default configuration and staged inputs;
     2. Automatically generated parameter-perturbation case(s) when Analytic App questions or `User.*` variables exist (verifying that config changes take effect without recompiling Python);
     3. Zero-row (header-only) boundary input case when local tabular inputs are present.
   - Compare all sink files (exact bytes or workbook/frame equivalence), exit codes, failure/warning outcomes, and lifecycle event logs.
   - Preserve `acceptance.json` top-level status keys (`native_vs_phase_one`, `phase_one_vs_phase_two`, `standalone_execution`, `status`) so existing automation and presentation workflows remain compatible.
3. **CLI, Presentation & Web Editor Integration**
   - `alteryx2python readable <source> --output <dir>` writes the modular Python package when `--output` is a directory path (or `--format package`), while supporting `--format single-file` when an explicit `.py` file path is requested by legacy callers.
   - `demo deliver` (`parity/presentation.py`) locates and opens the generated package's `pipeline.py` at the mapped semantic stage function line alongside its `config.toml`.
   - `webapp/backend.py` (`compile_workflow`) previews the clean `pipeline.py` in the Python tab and includes package `files` (`config.toml`, `pipeline.py`, `cli.py`, `io_utils.py`, etc.) in the compile payload.
4. **Benchmark & Spec Updates**
   - Update `examples/python_pipeline_comparison/compare.py` and `compare_app.py` to validate the modular Phase 2 package against handwritten Python references.
   - Update `.trellis/spec/backend/readable-python.md` and relevant docs (`docs/designer_delivery_demo.md`) to reflect config-decoupled package compilation and boundary differential verification.

## Acceptance Criteria

- Running `compare_app.py` compiles **one** reusable Phase 2 Python package for `transaction-app.yxwz` and runs all three cases (`defaults`, `alternate`, `empty`) strictly by swapping config files—achieving 100% match with Phase 1 and handwritten Python.
- `migrate --resume` / `verify-delivery` / `demo compare` & `demo deliver` pass end-to-end with zero staged paths or hardcoded answers inside `pipeline.py`.
- Full Python test suite (`pytest`) passes with >=80% coverage, and Web Editor TypeScript/unit tests (`npm --prefix webapp test`) pass.

## Out of Scope

- Live Designer GUI automation changes unrelated to Phase 2 artifact delivery.

# Technical Design: Multi-Case Boundary Differential Delivery & Integration

## 1. Decoupling Migration Staging from Phase 2 Codegen

In `alteryx2python/parity/migration.py` & `alteryx2python/parity/delivery.py`:
- `prepare_migration` already writes `migration.json` (`"source": str(source)`) and `inputs.json` (`[{"source": ..., "snapshot": ...}]`). Persist per-node input snapshot bindings (`node_id -> staged_relative_path`) in `native/manifest.json` (`staged_input_bindings`).
- `verify_delivery(native_directory, destination, ...)`:
  1. Keeps `native_vs_phase_one` comparison unchanged (comparing Designer probes against `phase_one.py` run on the staged workflow).
  2. Compiles Phase 2 package into `destination / "package"` from the **original source workflow** (falling back to `staged` only when standalone `prepare()` was called without `migration.json`), passing `reference_capture=first` so Option A data-driven refinements resolve deterministically!
  3. Writes `destination / "case_config.json"` overriding `inputs` to the staged snapshot paths, `outputs` to isolated verification directories, `parameters` to recorded `answers`, and `events` working directories/allowlists.
  4. Executes **Boundary Differential Suite**:
     - **Primary Case**: subprocess `python -I <package>/cli.py --config case_config.json` → compares sink artifacts, exit code, and JSONL workflow logs against `first` (`phase-one-capture.json`).
     - **Perturbed Parameter Case** (when `parameters` exist and inputs are available): perturbs each independent scalar parameter via `_alternate`, runs Phase 1 (`run_workflow_graph`) and Phase 2 subprocess with `perturbed_config.json` (**reusing the exact same compiled `destination / "package"`!**), and asserts identical sink outputs/outcomes.
     - **Empty-Input Case** (when CSV/Excel inputs exist and `observable` is normal success): generates header-only input copies in a temp case dir, runs Phase 1 and the same compiled Phase 2 package via `empty_config.json`, and asserts identical empty-case outputs.
  5. Records detailed multi-case results in `phase-one-vs-phase-two.json` and `standalone.json`, keeping `acceptance.json` status fields backward-compatible.

## 2. CLI, Presentation, and WebApp Surfaces

- **`cli.py` (`readable` subcommand)**:
  - Add `--format choices=("auto", "package", "single-file")` (default `"auto"`: directory path or no `.py` suffix → `ModularPackageGenerator` package; `.py` suffix → legacy single-file `ReadablePythonGenerator` unless `--format package` is passed).
- **`parity/presentation.py` (`_deliver`)**:
  - Prefer `directory / "package" / "pipeline.py"` and `directory / "package" / "manifest.json"` (with fallback to `phase_two.py` for pre-existing archived cases), resolving `node_id` via `manifest["nodes"]` (including optimized/fused stage line numbers) to open VS Code right at the clean stage function.
- **`webapp/backend.py` (`compile_workflow`)**:
  - Compile via `ModularPackageGenerator`, returning `python=artifact.files["pipeline.py"]`, `configToml=artifact.files["config.toml"]`, `packageFiles={k: v for k, v in artifact.files.items() if isinstance(v, str)}`, and `manifest=artifact.manifest`.

## 3. Rollback & Compatibility Notes

- Existing archived report directories with `phase_two.py` remain readable in `presentation.py`.
- Legacy single-file unit tests targeting `ReadablePythonGenerator().generate(workflow).source` continue working while new integration tests exercise `ModularPackageGenerator` and `verify_delivery` package outputs.

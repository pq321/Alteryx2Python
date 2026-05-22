# Select Tool First-Slice Checklist

## Scope

- Build the first canonical Alteryx migration slice for the `Select` tool only.
- Preserve Alteryx-style tool boundaries: one Python function represents one Alteryx tool instance.
- Target 100% line coverage for Select-related code in this slice.
- Use `alteryx2python/` as the canonical package root, with `alteryx_runtime/` retained only as a compatibility shim during transition.

## In Scope

- Minimal reusable runtime scaffolding required by `Select`.
- Initial canonical IR, runtime, comparison, registry, and documentation skeleton.
- `WorkflowContext` trace capture for node-level execution evidence.
- Schema helpers for column order and schema snapshots.
- `Select` configuration validation.
- `Select` behaviors:
  - keep fields
  - drop fields
  - rename fields
  - reorder fields
  - type changes
  - row count preservation
  - row order preservation
  - explicit error handling for invalid configuration
- Pytest suite with coverage scoped to Select-related modules.

## Out of Scope For This Slice

- Full workflow parser implementation
- Full canonical IR generation from XML
- Full graph execution engine
- Full formula engine
- Other Alteryx tools
- Golden-output workflow certification

## Constitutional Acceptance Criteria

- [x] One Python node function per Alteryx tool instance.
- [x] No optimization across tool boundaries.
- [x] Output is returned as an anchor map.
- [x] Output column order is explicit and deterministic.
- [x] Schema behavior is testable and recorded.
- [x] Row count is preserved.
- [x] Row order is preserved.
- [x] Unknown or invalid field references fail explicitly.
- [x] Type conversion behavior is explicit and tested.
- [x] Trace metadata is captured for node execution.
- [x] Unsupported or uncertain behavior is not silently approximated.
- [x] Select-related code reaches 100% line coverage.

## Done Definition

- [x] Runtime package created.
- [x] `select_tool(inputs, config, context)` implemented.
- [x] Tests cover success and failure paths.
- [x] `pytest` passes.
- [x] Coverage run reports 100% line coverage for Select-related modules.
- [x] Implementation notes clearly state what is intentionally deferred.

## Verification Notes

- `uv sync --extra test` succeeded against the internal Nexus package index after switching to copy mode for the project `.venv`.
- `uv run python -m pytest -o addopts= -q` passes with 18 tests.
- Standard-library `trace` reports full line execution for:
  - `alteryx_runtime.tools.select_tool`
  - `alteryx_runtime.context`
  - `alteryx_runtime.schemas.schema`
- `pytest-cov` and `coverage run` trigger an environment-specific import issue in this workspace, so the 100% line result was verified with `trace` instead.

## Deferred Notes

- Duplicate output field names are treated as invalid in this slice unless explicitly supported later by a more precise Alteryx semantic layer.
- Type conversions are intentionally strict and limited to explicit conversion modes supported by this first implementation.
- This slice is `NOT CERTIFIED`; it is a focused foundation for one tool implementation.
- Optimizer modules exist only as disabled placeholders and must not be used for canonical baseline migration.
# Fixtures Layout

- `tool_inputs/`: reusable input datasets for individual tool semantics.
- `golden_outputs/`: approved Alteryx outputs for comparison.
- `yxmd/`: source workflow artifacts used in parser and integration tests.
- `expected_ir/`: serialized expected IR snapshots for parser validation.
- `real_workflows/`: documentation and helper files for real Alteryx workflows checked into the repo.

The directories are intentionally created before they are populated so fixtures stay centralized as tool coverage expands.

## Real Workflow Strategy

- Real sample workflows are committed under `examples/` so they remain visible as primary source artifacts rather than hidden test-only inputs.
- Tests should reference real workflow files from `examples/` by path instead of copying the binary or XML payload into `tests/fixtures/`.
- `tests/fixtures/real_workflows/` holds documentation, sanitized notes, helper data, and future golden outputs derived from those real workflows.
- Synthetic parser and tool fixtures should stay separate from real workflow assets so regression scope remains obvious.

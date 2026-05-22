# Fixtures Layout

- `tool_inputs/`: reusable input datasets for individual tool semantics.
- `golden_outputs/`: approved Alteryx outputs for comparison.
- `yxmd/`: source workflow artifacts used in parser and integration tests.
- `expected_ir/`: serialized expected IR snapshots for parser validation.

The directories are intentionally created before they are populated so fixtures stay centralized as tool coverage expands.

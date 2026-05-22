# Real Workflow Fixtures

This directory tracks metadata and supporting assets for real Alteryx workflows used by parser and integration tests.

## Current Strategy

- The source workflow file lives under `examples/sample_workflows/`.
- Tests reference the source file in `examples/` directly.
- This directory is reserved for:
  - sanitized notes about external dependencies
  - derived fixture inputs
  - expected outputs
  - partial subgraph test data

## Current Real Workflow Target

- `examples/sample_workflows/MIFID II.yxwz`

## Known External Dependencies

- `DownloadData.xlsx|||output$`
- `mapping.csv`
- `MIFID output.xlsx|||Sheet1`
- `ROB-102928 Input template - EQ.xlsx|||Sheet1$`

None of those external files are currently present in the repository, so M1 only validates workflow intake and XML readability, not executable data access.

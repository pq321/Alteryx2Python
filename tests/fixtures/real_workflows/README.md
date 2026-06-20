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
- `D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd`
- `D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd`

## Known External Dependencies

- `DownloadData.xlsx|||output$`
- `mapping.csv`
- `MIFID output.xlsx|||Sheet1`
- `ROB-102928 Input template - EQ.xlsx|||Sheet1$`

None of those external files are currently present in the repository, so M1 only validates workflow intake and XML readability, not executable data access.

## Derived Fixture Inputs

- `mifid_download_data.csv` is a sanitized CSV fixture for the first executable MIFID subgraph.
- It replaces the unavailable node `18` Excel dependency during tests.
- The columns mirror the input surface consumed by nodes `21 -> 24`: `Cookie`, `URL`, `DownloadHeaders`, and `DownloadData`.
- The JSON payload intentionally contains both `result.exceptions.0.*` fields and one non-matching `status` field so the downstream Filter `True` and `False` anchors are both exercised.
- `mifid_mapping.csv` is a sanitized mapping fixture for MIFID node `32`.
- The mapping fixture is intentionally small: it maps only `assetClass` and `buyerId`, which are the fields needed to prove the first reshape/join/union slice.
- `mifid_target36_expected.csv` is the first golden evidence fixture. It captures the stable output columns produced by the real parsed MIFID branch through node `36`.
- `text_input_expected.csv` is the first complete official one-tool workflow golden fixture. It captures the embedded output of `Text_Input.yxmd` node `98` with empty cells preserved as empty strings.
- `combine_customer_profile_expected.csv` is the first complete official multi-tool workflow oracle. It was copied from an Alteryx Engine CSV output for Basic `01 Combine 2 Spreadsheets Containing Customer Data.yxmd`.

# Testing Strategy

Testing is split by responsibility rather than by implementation convenience.

Current layout:

- `tests/test_tools`: tool-level semantic tests
- `tests/test_runtime`: runtime and executor tests
- `tests/test_contracts`: node-level contract derivation and validation tests
- `tests/test_ir`: IR-level tests
- `tests/test_parser`: parser contract tests
- `tests/test_expressions`: expression-layer tests
- `tests/test_generator`: generator tests
- `tests/test_integration`: workflow-level tests
- `tests/fixtures`: reusable input, golden output, YXMD, and expected IR assets

Implemented tool slices now include:

- `Select`
- `DbFileInput`
- `Formula`
- `Filter`
- `JSONParse`
- `RecordID`
- `Sort`
- `CrossTab`
- `DynamicRename`
- `Transpose`
- `Join`
- `Union`
- `TextInput`

The current E2E-style integration coverage parses official one-tool-at-a-time Alteryx samples from `D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time`, extracts supported tool configs and embedded Text Input data where available, and executes the matching Python tool implementation. `DbFileInput` also executes the official CSV input from `Input_Data.yxmd`. These tests are not certification-grade golden-output comparisons yet; they are migration smoke/E2E checks for config extraction plus supported semantics.

Runtime graph coverage includes synthetic `WorkflowIR` DAGs for:

- linear tool pipelines
- Filter `True` and `False` branch routing
- target-node subgraph execution
- skipped frontier node warnings
- missing upstream anchor failures
- unsupported tool failures
- cycle detection
- trace ordering
- contract evidence on executed nodes
- contract failure before bad intermediate outputs continue downstream

Contract coverage includes:

- declared output anchors are emitted
- output anchors contain pandas DataFrames
- parser-provided expected output schema is enforced when strict mode is enabled
- `Select` preserves row count and emits configured/reordered/renamed columns
- `Formula` preserves row count and preserves/appends formula columns
- `Filter` preserves schema on `True` and `False` anchors and partitions input rows
- `Union` emits by-name union columns and summed row count
- `Join` emits `Join`, `Left`, and `Right` anchors and keeps unjoined row counts bounded by input row counts

The official `Input_Data.yxmd` CSV input node is also executed through `run_workflow_graph` after parsing.

The first real workflow subgraph test parses `examples/sample_workflows/MIFID II.yxwz`, redirects node `18` to `tests/fixtures/real_workflows/mifid_download_data.csv`, and executes target node `24`. This proves parser -> IR -> runtime execution for the real chain `DbFileInput -> Select -> JSONParse -> Formula -> Filter` while keeping unavailable local Excel dependencies out of the repository.

The first real reshape test uses the same workflow plus `tests/fixtures/real_workflows/mifid_mapping.csv` for node `32`, then executes to target node `36`. This covers `CrossTab -> DynamicRename -> RecordID -> Transpose -> Join -> Union -> Formula` on the real parsed MIFID branch.

M9 adds the first repeatable golden-output comparison for the target `36` branch. The expected evidence lives in `tests/fixtures/real_workflows/mifid_target36_expected.csv` and is compared with `compare_dataframes` after selecting the branch's stable evidence columns.

M10 adds `build_dataframe_comparison_report`, which wraps dataframe diffs into a machine-readable dictionary plus a compact human summary. Certification docs now define the minimum evidence expected for a workflow slice.

M11 generator coverage includes:

- generated imports and embedded node IDs
- synthetic generated-code execution
- parse -> generate -> execute for the real MIFID target `24` slice
- parse -> generate -> execute for the official `Text_Input.yxmd` target `98` output

M13 adds the first complete official one-tool workflow golden comparison:

- source: `D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd`
- executable target: node `98` (`TextInput`)
- expected output: `tests/fixtures/real_workflows/text_input_expected.csv`
- comparison: `compare_dataframes` with string/object values and empty cells preserved as empty strings

This is a complete data-output certification for the official sample because the workflow has no data edges and no output/browse sink; its only executable data node is the embedded `TextInput`.

M14 adds the first complete official multi-tool workflow golden comparison:

- source: `D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd`
- inputs:
  - `D:/Alteryx/Samples/data/StartHereData/Excel.CustomerLocationData.xlsx`
  - `D:/Alteryx/Samples/data/StartHereData/Excel.CustomerResponderData.xlsx`
- oracle output: `tests/fixtures/real_workflows/combine_customer_profile_expected.csv`
- runtime path: parse -> execute target node `23` -> write CSV -> compare with `compare_dataframes`
- generator path: parse -> generate -> execute generated code target node `23` -> write CSV -> compare
- file-level evidence: generated CSV bytes must match the oracle bytes
- certification gate: executed node order must pass `assert_nodes_certifiable`

This test covers a real multi-tool workflow using Excel input, Select, Join, Sort, and CSV output.

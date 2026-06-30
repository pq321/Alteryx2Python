# Certification Evidence

Certification is not just successful execution. A workflow slice needs explicit comparison evidence, and the strongest evidence is layered from each executable node outward.

Final Excel/CSV equality remains valuable, but it is only the outermost assertion. Every executable Alteryx tool can also produce node-level contract evidence for its inputs, output anchors, schemas, row counts, and tool-specific invariants.

Current baseline evidence for a slice includes:

- source workflow path and target node
- input fixture paths
- golden output fixture path
- executed node IDs
- skipped frontier warnings
- node-level contract evidence when available
- emitted output anchors per node
- per-anchor row count
- per-anchor column order and names
- per-anchor column dtypes
- row count
- column order and names
- column dtypes after any documented fixture normalization
- cell-level value differences
- human-readable comparison summary
- machine-readable comparison report

## Evidence Layers

Certification reports should distinguish these layers:

1. parser evidence: the source workflow parsed into stable `WorkflowIR`
2. routing evidence: graph edges routed anchor outputs to expected input anchors
3. tool contract evidence: each executed tool emitted its declared anchors
4. schema evidence: each output anchor matched inferred columns and dtypes, plus parser-provided expected schema when strict enforcement is enabled
5. shape evidence: row-count invariants held for row-preserving, partitioning, joining, or unioning tools
6. semantic evidence: tool-specific assertions passed where implemented
7. oracle evidence: target/final output matched a fixture produced by Alteryx outside this Python runtime

A node can be useful without full oracle evidence. For example, a `Select` node can pass inferred contract assertions for column order and row preservation even when no separate Alteryx intermediate export exists.

## Node-Level Contract Evidence

Each executed node may produce `ContractEvidence`:

- `node_id`
- `tool_type`
- input schemas by anchor
- output schemas by anchor
- assertion results with expected value, actual value, pass/fail, and diagnostic message

Initial assertion vocabulary:

- `anchor_emitted`
- `no_undeclared_output_anchors`
- `output_is_dataframe`
- `column_order_equals`
- `row_count_equals_input`
- `row_count_equals_sum_of_anchors`
- `row_count_equals_sum_of_inputs`

Tool-specific contracts start narrow and explicit. They are not claims of full Alteryx parity.

Parser-provided `expected_output_schema` is source metadata, not always a hard oracle. It may differ from sanitized fixtures or explicit input overrides. Runtime enforcement of that metadata is strict-mode behavior through `enforce_expected_output_schema=True`; inferred tool contracts still run by default.

The first evidence-backed slice is the MIFID target `36` branch:

- source: `examples/sample_workflows/MIFID II.yxwz`
- inputs: `tests/fixtures/real_workflows/mifid_download_data.csv`, `tests/fixtures/real_workflows/mifid_mapping.csv`
- expected output: `tests/fixtures/real_workflows/mifid_target36_expected.csv`
- comparison helper: `build_dataframe_comparison_report`

The first complete official one-tool workflow data-output certification is `Text_Input.yxmd`:

- source: `D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd`
- target node: `98`
- executable tool: `TextInput`
- expected output: `tests/fixtures/real_workflows/text_input_expected.csv`
- comparison helper: `compare_dataframes`
- generator evidence: parse -> generate -> execute generated Python -> compare target `98`

This workflow contains documentation `TextBox` nodes and one executable embedded data node. Because it has no data edges or output sink, target node `98` is treated as the workflow's complete data output for certification.

The first complete official multi-tool workflow certification is Basic `01 Combine 2 Spreadsheets Containing Customer Data.yxmd`:

- source: `D:/Alteryx/Samples/en/04 Basic/01 Combine 2 Spreadsheets Containing Customer Data.yxmd`
- input files:
  - `D:/Alteryx/Samples/data/StartHereData/Excel.CustomerLocationData.xlsx`
  - `D:/Alteryx/Samples/data/StartHereData/Excel.CustomerResponderData.xlsx`
- tools executed: `DbFileInput -> Select -> Join -> Sort -> DbFileOutput`
- executed node order: `1, 2, 7, 3, 4, 6, 23`
- Alteryx oracle fixture: `tests/fixtures/real_workflows/combine_customer_profile_expected.csv`
- comparison helper: `compare_dataframes`
- generator evidence: parse -> generate -> execute generated Python -> write CSV -> compare to oracle
- file evidence: generated CSV bytes match the oracle CSV bytes for this workflow

This is the first evidence that a real multi-tool official workflow can be converted through the canonical generated Python path and reproduce an externally captured Alteryx CSV oracle byte-for-byte for the observed configuration.

Certification precheck:

- A workflow path must pass `assert_nodes_certifiable` before it can be described as certified.
- Certification is tool-and-config scoped: `assert_nodes_certifiable` checks both the tool type and the observed normalized config shape.
- `supports_certification=True` means the tool may participate in workflow-level golden-output certification only when its normalized config passes the certification predicate.
- Passing node-level contracts means the Python runtime output satisfied the implemented assertions for that node and config. It does not by itself prove final-output or oracle equivalence.
- Examples of rejected deferred config shapes include YXDB input, Excel output, Join by record position, and unsupported Sort orders.
- Passing the gate does not mean the tool fully reproduces every Alteryx option, warning, error, type coercion, or file format variant.

Known current limits:

- MIFID evidence is branch evidence, not full workflow certification.
- `Text_Input.yxmd` is full data-output evidence for one official one-tool sample, not evidence for arbitrary workflows.
- Excel input is supported for observed sheet references; Excel output remains deferred.
- YXDB, spatial, reporting, macro, and many Advanced tools remain deferred.
- The Basic Combine byte match proves this CSV output configuration, not all `DbFileOutput` CSV options.
- MIFID and Text Input golden fixtures were produced from the implemented slice semantics.
- Basic Combine golden output was copied from an Alteryx CSV output supplied for this certification pass. The project does not invoke Alteryx Engine APIs or `AlteryxEngineCmd`; oracle fixtures are captured manually or by external environments.

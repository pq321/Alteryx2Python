# TextInput Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- no input anchors
- one output anchor named `Output`
- embedded field names from `Fields/Field/@name`
- embedded row values from `Data/r/c`
- empty XML cells (`<c/>`) are preserved as null, as observed in Designer 2025.1 YXDB output
- explicit empty strings supplied to the runtime remain distinct from null
- values are emitted as `object`/string data without numeric or date inference
- execution trace with output schema

Deferred semantics:

- full Alteryx type inference shown in the Results metadata view
- user-edited field type overrides, if present in other Text Input XML shapes
- conversion warning/error behavior for typed Text Input values
- locale-specific parsing for dates and numbers

Certification note:

- `D:/Alteryx/Samples/en/02 Learn_one_tool_at_a_time/01 In Out/Text_Input.yxmd` is the first official full data-output workflow target.
- The workflow contains documentation `TextBox` nodes plus one executable `TextInput` node (`98`) and no data edges.
- Certification executes target node `98` and compares the output to `tests/fixtures/real_workflows/text_input_expected.csv`.

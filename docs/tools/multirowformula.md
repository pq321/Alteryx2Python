# MultiRowFormula Tool Semantics

Maturity: `L2_BASIC_IMPLEMENTATION`

Supported baseline behavior:

- Reads from `Input` and writes to `Output`.
- Updates an existing field when `update_field` is true.
- Creates a new field when `update_field` is false.
- Evaluates rows sequentially, so references to fields created by the tool can read previously computed rows.
- Supports grouped window reset using `group_by_fields`.
- Supports `[Row-1:Field]`, `[Row-2:Field]`, and forward/backward references up to the configured `num_rows`.
- Supports `other_rows` modes used in samples:
  - `Empty`: missing window rows become null, or zero for missing numeric target fields.
  - `Nearest`: missing window rows reuse the nearest row in the current group.

Expression support is shared with Formula and includes the sample-specific functions `Average`, `DateTimeDiff`, `Trim`, and `Null`.

Known gaps:

- Output typing is a pragmatic pandas coercion for common numeric and boolean field types.
- Only row offsets within the configured `num_rows` range are materialized.
- Full Alteryx behavior for every `OtherRows` mode and field metadata is not yet modeled.

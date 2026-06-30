# DynamicSelect Tool Semantics

Maturity: `L2_BASIC_IMPLEMENTATION`

Supported baseline behavior:

- Reads from `Input` and writes to `Output`.
- `FieldTypes` mode selects columns whose inferred Alteryx type appears in `field_types`.
- `Formula` mode evaluates the expression once per input column against a schema row.
- Formula schema fields include `Name`, `Type`, `FieldNumber`, `IsString`, `IsNumeric`, `IsDateTime`, and `IsStringOrDate`.
- Formula results can be boolean values or string `"True"` / `"False"`.

Known gaps:

- Type inference is derived from pandas dtypes and does not reproduce every Alteryx metadata field.
- Only sample-backed formula helpers are currently covered.
- Action-input driven interface updates are parsed but not executed.

# DataCleansePro Tool Semantics

Maturity: `L2_BASIC_IMPLEMENTATION`

Supported baseline behavior:

- Reads from `Input` and writes to `Output`.
- Selects configured fields from the native `Fields/Field` configuration.
- Reuses the Data Cleansing cleanup semantics for:
  - null row and null column removal
  - null replacement with blank or zero
  - leading/trailing whitespace cleanup
  - duplicate whitespace cleanup
  - all-whitespace, letter, number, and punctuation removal
  - case conversion

Known gaps:

- `RemoveHTMLTags`, `RemoveInvisibleCharacters`, custom letters/numbers/punctuations, and exception character sets are parsed as unsupported options for now.
- Type-specific Alteryx output metadata is not reproduced; pandas dtypes are inferred from the transformed frame.

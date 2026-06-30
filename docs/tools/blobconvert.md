# BlobConvert Tool Semantics

Maturity: `L2_BASIC_IMPLEMENTATION`

Supported baseline behavior:

- Reads from `Input` and writes to `Output`.
- Converts the configured field in place.
- `to_blob=false` supports:
  - `Base64`: bytes to Base64 text
  - `Hex` / `HEX`: bytes to uppercase hexadecimal text
  - `MD5`: bytes to lowercase MD5 digest
  - `Text`: bytes to decoded text
  - `ReportSnippet`: bytes to a simple embedded data URI image snippet
- `to_blob=true` supports:
  - `Base64`: Base64 text to bytes
  - `Hex` / `HEX`: hexadecimal text to bytes
  - `Text`: text to bytes
- `UTF16` and UTF-8 text code pages are recognized for sample workflows.

Known gaps:

- Report snippet output is a deterministic data URI approximation, not a full Alteryx reporting object.
- File/blob input and output tools remain separate concerns; this tool only converts field values already present in the input frame.

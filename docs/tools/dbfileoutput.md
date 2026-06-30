# DbFileOutput Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- one input anchor named `Input`
- no output anchors
- Alteryx file reference parsing for `path|||selector`
- CSV output for `FileFormat=0`
- `MaxRecords`
- parent directory creation
- execution trace with resolved path and input schema

Deferred semantics:

- Excel output
- YXDB output
- database/data-connection outputs
- output options beyond overwrite-style CSV writes
- preserving workbook formatting, sheets, and named ranges

Certification notes:

- The observed CSV output configuration can participate in workflow-level golden-output certification.
- The Basic Combine workflow currently verifies byte-for-byte CSV parity for that specific output config.
- This does not certify every delimiter, quoting, encoding, BOM, newline, null, or output-option variant.

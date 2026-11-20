# DbFileInput Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- no input anchors
- one output anchor named `Output`
- Alteryx file reference parsing for `path|||selector`
- relative path resolution through `base_dir`
- CSV input for `FileFormat=0`
- Excel sheet input for `FileFormat=25`
- CSV delimiter option through Alteryx `Delimeter`
- `HeaderRow=True`
- blank CSV headers use `Field_1`, `Field_2`, and so on by column position
- blank Excel headers use `F1`, `F2`, and so on. Explicit cell ranges retain their selected width
- duplicate headers use Designer naming rules and reserve the other names in the header row
- `FirstRowData=True` no-header mode with generated `F1`, `F2`, ... field names
- one-based `ImportLine`
- `RecordLimit`
- code page `28591` mapped to `iso-8859-1`
- execution trace with resolved path and output schema

Deferred semantics:

- YXDB input
- Excel named ranges
- Excel `<List of Sheet Names>`
- full Alteryx type coercion from `MetaInfo`
- database/data-connection inputs
- search subdirectories and wildcard input

Certification notes:

- The observed CSV and Excel sheet input modes can participate in workflow-level golden-output certification.
- This does not certify every DbFileInput file format, driver, metadata, or conversion behavior.

Excel sheet input:

- The tool has a sheet-reading path for `.xlsx`/`.xls` references ending in a sheet selector such as ``|||`Sheet1$``.
- This path depends on `openpyxl`, which is now a project dependency.
- If `FirstRowData=True`, the first row is treated as data and fields are named `F1`, `F2`, and so on.
- A worksheet read includes its defined columns. An explicit range such as `|||Sheet1$A1:D10` also includes undeclared columns within that range.

[Native blank-header comparisons](evidence/2026-11-20/blank-headers-data-cleansing/README.md)

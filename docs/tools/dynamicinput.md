# DynamicInput

`ReadList / Path` reads CSV or XLSX files named by a field on `Input`.
It reads each distinct path in path order, using the template's format and
read options. The `Output` contains file records. Empty lists use the
template schema, and mismatched columns fail explicitly.

Phase One and standalone Phase Two share this operation. SQL modifications,
other path actions, filename metadata fields and formats outside CSV/XLSX
are blocked. Use a local Designer fixture for native verification.

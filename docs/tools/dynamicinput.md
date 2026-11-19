# DynamicInput

`ReadList / Path` reads CSV or XLSX files named by a field on `Input`.
It reads each distinct path in path order, using the template's format and
read options. The `Output` contains file records. Empty lists use the
template schema, and mismatched columns fail explicitly.

`Suffix`, `Prefix`, and `FileName` use the saved template. For CSV they
change the file's stem and retain the template extension. For XLSX with a
worksheet selector, they change the selector inside the template workbook.
Step 2 stages the resulting references before opening Designer.

Phase One and standalone Phase Two share these operations. SQL modifications,
filename metadata fields, and template formats outside CSV/XLSX remain blocked.

# TextToColumns

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Input: `Input`
- Output: `Output`

Implemented semantics:

- split configured field using Alteryx delimiter strings
- column output mode with `RootName` and `NumFields`
- imported configurations with `NumFields=1` split into rows. For older Python IR without an explicit mode, the legacy row-splitting flag is retained.
- imported flags support ignoring delimiters inside double quotes, single quotes, parentheses, and brackets, and skipping empty segments.
- column overflow supports `Last`, `Warn`, `Ignore`, and `Error`.
- imported configurations retain a null input as null and preserve empty tokens between consecutive delimiters.

Deferred semantics:

- exact native diagnostics and nested/unclosed bookend behavior

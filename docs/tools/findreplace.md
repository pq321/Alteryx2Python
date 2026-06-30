# FindReplace

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Targets input: `Targets`
- Lookup input: `Source`
- Output: `Output`

Implemented semantics:

- exact string search against `FieldSearch`
- `FindAny`, `FindBegin`, `FindEnd`, and whole-field modes
- optional case-insensitive matching
- optional whole-word matching
- `Replace` mode using `ReplaceFoundField`
- `Append` mode using configured `ReplaceAppendFields`

Deferred semantics:

- fuzzy matching
- regex-specific modes
- exact Alteryx multi-match ordering for conflicting append values

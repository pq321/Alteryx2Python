# JSON Parse Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- parse JSON from a configured input field
- flatten nested object keys using dot notation
- flatten arrays using numeric path components
- output `JSON_Name` and `JSON_ValueString`
- optionally include original input columns in output rows
- explicit failure for missing JSON field or malformed JSON

Deferred semantics:

- typed multi-field output for `SingleField=False`
- exact Alteryx path notation for all array/object cases
- binary/blob JSON payloads
- malformed-row recovery modes
- golden-output certification against official examples

# DateTime

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics:

- parse formatted strings to ISO dates or times when `IsFrom=False`
- format ISO-like dates/times to configured strings when `IsFrom=True`
- sample formats including `Month dd, yyyy`, `day, dd Month, yyyy`, `day, Month dd, yyyy`, `MM-dd/yyyy`, and `HH:mm:ss`

Deferred semantics:

- non-English month/day names
- complete Alteryx custom format vocabulary

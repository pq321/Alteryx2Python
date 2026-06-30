# RegEx

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics:

- `Match`
- `Replace` with `$1`-style capture references
- `ParseComplex` capture groups
- `ParseSimple` repeated matches into numbered output fields
- optional case-insensitive matching

Deferred semantics:

- split-to-rows parse simple mode
- exact Alteryx unmatched/error-row behavior

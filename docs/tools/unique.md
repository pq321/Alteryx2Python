# Unique

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Input: `Input`
- Unique output: `Unique`
- Duplicate output: `Duplicate`

Implemented semantics:

- first row for each configured key goes to `Unique`
- later rows with the same configured key go to `Duplicate`
- all columns are preserved

Deferred semantics:

- locale/collation-specific comparisons

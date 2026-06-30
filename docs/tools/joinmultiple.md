# JoinMultiple

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Input: repeated `Input`, `Input_2`, ...
- Output: `Output`

Implemented semantics:

- maps input order to Alteryx-style `#1`, `#2`, ... connections
- supports inner joins on configured fields
- supports record-position joins
- prefixes output columns as `Input_#N_<field>`
- applies configured select-field renames when present

Deferred semantics:

- exact non-joined-row behavior for every `OutputJoinOnly` mode
- full Alteryx select projection compatibility

# CrossTab Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- one input anchor named `Input`
- one output anchor named `Output`
- grouping by configured group fields
- header field values become output columns
- data field values populate pivoted cells
- imported Designer definitions preserve all configured actions. Supported actions include `Sum`, `Avg`, `Count` (without nulls), `First`, `Last`, `Concat`, row and column percentages, and row and column totals.
- imported definitions sort group and header keys, combine header values differing only by case, and prefix generated fields with the action as applicable.
- saved concatenation separators and field sizes are parsed for imported definitions.
- earlier Python IR with only `method` retains its first-appearance order and original aggregation behavior.

Deferred semantics:

- distinct counts, count including nulls, and other unsupported actions
- complete locale, field-name collision, and warning parity
- complete Alteryx metadata/type propagation
- certification against golden Alteryx output

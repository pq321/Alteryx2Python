# Filter Tool

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- one input anchor named `Input`
- two output anchors named `True` and `False`
- row-order preserving boolean split
- field references, literals, comparisons, boolean `AND`/`OR`, and unary `!`
- `IsNull`, `StartsWith`, `REGEX_Match`, and `UPPERCASE` through the controlled expression layer

Deferred semantics:

- date/time simple filter operators
- period-based filter operators
- full Alteryx null/type coercion semantics
- optimizer shortcuts or predicate pushdown
- golden-output certification against official examples

## Contract

Inputs:

- `Input`: pandas DataFrame

Outputs:

- `True`: rows where the expression evaluates truthy
- `False`: rows where the expression evaluates falsy

Assertions:

- `True` and `False` anchors are emitted
- both outputs are pandas DataFrames
- both outputs preserve the input column order
- `True` row count plus `False` row count equals `Input` row count

Evidence status:

- runtime contract evidence is emitted on `NodeResult.contract_evidence`
- no standalone official golden-output certification yet

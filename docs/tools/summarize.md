# Summarize

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics:

- `GroupBy`
- `Sum`, `Count`, `CountNonBlank`, `CountBlank`
- `CountNonNull`, `CountNull`, `CountDistinct`, `CountDistinctNonNull`. An empty string is a non-null value. Distinct counts with nulls include a single null value when present.
- `Min`, `Max`, `Avg`, `Median`, `Mode`, `StdDev`, `Variance`
- `First`, `Last`, `Longest`, `Shortest`
- `Concat` with configured start, separator, and end strings

Deferred semantics:

- spatial summarize actions
- exact locale/collation-specific behavior

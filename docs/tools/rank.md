# Rank

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics:

- sort-field parsing
- optional group reset
- `Ordinal`, `Dense`, `Standard`, `Competition`, and `Fractional` rank modes. Designer saves Modified Competition Ranking as `Competition` and assigns tied rows the last rank in the tie.
- Imported Designer configurations emit the original ranking field names, in configured mode order.

Deferred semantics:

- exact multi-column tie behavior beyond primary sort field

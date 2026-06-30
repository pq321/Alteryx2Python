# CreatePoints Tool

## Coverage

- Parses `Fields` attributes `fieldX` and `fieldY` plus `Mode` from one-tool sample workflows.
- Supports `Double` coordinate mode.
- Preserves all input columns and appends a spatial placeholder field, defaulting to `Centroid`.
- Emits points as WKT strings in `POINT (x y)` order.
- Emits null for rows where either coordinate cannot be converted to a number.

## Deferred

- Native Alteryx spatial object binary encoding is not reproduced.
- Coordinate systems, projection metadata, and non-`Double` modes are not implemented.

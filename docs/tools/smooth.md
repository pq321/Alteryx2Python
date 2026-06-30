# Smooth Tool Semantics

`Smooth` is implemented as a deterministic WKT-oriented baseline for official sample workflows.

Supported behavior:

- Reads one `Input` anchor and emits one `Output` anchor.
- Requires the configured spatial field to exist.
- Preserves input rows.
- Adds `SpatialObj_Smooth` by applying a simple moving-average pass over WKT coordinate pairs.
- Honors `IncludeSourceInOutput` by omitting the source spatial field when false.
- Records passes, maximum radius, units, and post-generalize settings as execution evidence.

Known limits:

- This is a lightweight coordinate smoothing baseline, not Alteryx's native spatial smoothing algorithm.
- Native Alteryx spatial object binary formats are not decoded.
- Maximum radius, units, and post-generalize settings are parsed and recorded but do not constrain the simple moving-average output.

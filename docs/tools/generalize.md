# Generalize Tool Semantics

`Generalize` is implemented as a deterministic WKT-oriented baseline for official sample workflows.

Supported behavior:

- Reads one `Input` anchor and emits one `Output` anchor.
- Requires the configured spatial field to exist.
- Preserves input rows.
- Adds `SpatialObj_Generalize` by copying the configured spatial field with repeated adjacent coordinate pairs removed.
- Honors `IncludeSourceInOutput` by omitting the source spatial field when false.
- Records threshold, units, and layerwise settings as execution evidence.

Known limits:

- This is not a topology-preserving Douglas-Peucker implementation.
- Native Alteryx spatial object binary formats are not decoded.
- Threshold and units are parsed and recorded but do not change geometry beyond deterministic duplicate-coordinate compaction.

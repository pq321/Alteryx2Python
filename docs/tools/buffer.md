# Buffer Tool Semantics

`Buffer` is implemented as a deterministic WKT baseline for official sample workflow conversion.

Supported behavior:

- Reads one `Input` anchor.
- Parses the configured spatial field as WKT.
- Supports fixed buffer size and field-driven buffer size.
- Converts Miles, Kilometers, Meters, and Feet into approximate degrees.
- Emits `SpatialObj_Buffer`.
- Preserves or omits the source spatial field based on `IncludeSourceInOutput`.

Limits:

- This is not a full spatial engine.
- Multi-point polygons and lines are buffered by expanding their bounding box.
- Single points are buffered as approximate circular polygons.
- Native Alteryx curve smoothing, topology repair, holes, and generalization are not implemented.

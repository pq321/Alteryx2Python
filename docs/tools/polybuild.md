# PolyBuild Tool Semantics

`PolyBuild` is implemented as a deterministic WKT polygon-building baseline for official sample workflow conversion.

Supported behavior:

- Reads one `Input` anchor.
- Parses the configured WKT spatial field and keeps the first coordinate from each spatial object.
- Groups records by `GroupField` when configured.
- Supports `SequencePolygon` by sorting by `SequenceField` and connecting points in order.
- Supports `ConvexHull` with a monotonic-chain convex hull.
- Emits one row per group with `SpatialObj_Built`.

Limits:

- This is not a full spatial engine.
- Curve, multipart, hole, invalid-shape repair, and native Alteryx spatial object semantics are not implemented.
- Groups with fewer than three usable points produce a null built spatial object.

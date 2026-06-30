# TradeArea Tool Semantics

`TradeArea` is implemented as a deterministic WKT radius-polygon baseline for official sample workflows.

Supported behavior:

- Reads one `Input` anchor and emits one `Output` anchor.
- Uses the configured spatial object field as the trade-area source.
- Parses WKT-like coordinate pairs and uses their average coordinate as the center.
- Parses `Radii` values separated by commas. For range labels such as `2-5`, the outer radius is used for the polygon and the original label is preserved in `RadiusSize`.
- Emits one output row per input row per configured radius.
- Adds `SpatialObject_TradeArea` as an approximate circular `POLYGON` and `RadiusSize` as the original radius label.
- Honors `includeOut="False"` by omitting the source spatial field from output rows.

Known limits:

- The polygon is an approximation based on numeric coordinates. Miles, kilometers, and meters are converted to rough degree offsets for sample workflow portability.
- `Minutes` drive-time trade areas are approximated like radius polygons and do not call routing data.
- `noOverlap` is parsed and recorded but does not clip overlapping polygons.
- Radius-from-field mode is explicitly deferred.

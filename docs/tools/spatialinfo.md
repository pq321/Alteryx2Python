# SpatialInfo Tool Semantics

`SpatialInfo` is implemented as a deterministic WKT-based baseline for official sample workflows.

Supported behavior:

- Reads one `Input` anchor and emits one `Output` anchor.
- Preserves all input rows and columns.
- Parses WKT-like `POINT`, `LINESTRING`, `POLYGON`, and `MULTIPOLYGON` coordinate pairs from the configured spatial field.
- Supports sample `SelectedItems` values:
  - `AreaMi` adds `AreaSqMi` with planar polygon area.
  - `CentroidObj` adds `Centroid` as WKT `POINT`.
  - `CentroidXY` adds `CentroidX` and `CentroidY`.
  - `RectObj` adds `BoundingRect_TopLeft` and `BoundingRect_BottomRight`.
  - `RectPolygon` adds `BoundingRect`.
  - `RectXY` adds `BR_TopLeft_X`, `BR_TopLeft_Y`, `BR_BottomRight_X`, and `BR_BottomRight_Y`.
  - `EndPointsObj` adds `StartPoint` and `EndPoint`.
  - `EndPointsXY` adds `StartPoint_X`, `StartPoint_Y`, `EndPoint_X`, and `EndPoint_Y`.

Known limits:

- Area is planar over the numeric coordinates in the WKT string. It is not a geodesic square-mile calculation and does not replace a GIS engine.
- Unsupported or malformed spatial values preserve the row and emit null derived values.
- Native Alteryx spatial object binary formats are not decoded.

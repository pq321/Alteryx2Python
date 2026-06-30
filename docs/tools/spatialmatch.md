# SpatialMatch Tool Semantics

`SpatialMatch` is implemented as a deterministic WKT bounding-box baseline for official sample workflows.

Supported behavior:

- Reads `Targets` and `Universe` anchors and emits a `Matched` anchor.
- Parses the configured `Target` and `Universe` spatial object fields.
- Supports sample `Method` values:
  - `Contains`: target bbox contains universe bbox.
  - `Within`: universe bbox contains target bbox.
  - `Intersects`: target and universe bboxes overlap.
- Outputs joined rows with `Target_` and `Universe_` prefixes.
- Applies `SelectConfiguration` entries, including `*Unknown`, selected flags, and renames.
- When `IntersectPoly` is enabled, adds an approximate bbox-overlap polygon in `IntersectPoly`.

Known limits:

- Matching uses bounding boxes derived from WKT coordinate pairs. It is not a full topological GIS operation.
- Native Alteryx spatial object binary formats are not decoded.
- External universe files embedded in the tool configuration are parsed as metadata only; runtime execution expects a `Universe` DataFrame anchor.

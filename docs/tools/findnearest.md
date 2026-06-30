# FindNearest Tool Semantics

`FindNearest` is implemented as a deterministic WKT nearest-neighbor baseline for official sample workflow conversion.

Supported behavior:

- Reads `Targets` and `Universe` input anchors.
- Uses the configured target and universe spatial fields.
- Uses the average of each WKT object's coordinate pairs as its center.
- Computes straight-line haversine distance.
- Respects `HowMany`, `MaxDistance`, `MaxDistanceUnits`, and `Ignore0` for Miles/Kilometers/Meters/Feet.
- Emits prefixed `Target_*` and `Universe_*` fields plus `FindNearestRank`, `Distance*`, and `Direction`.
- Applies the configured `SelectConfiguration` to the matched output.

Limits:

- This is not a full spatial engine.
- Direct universe-file loading is parsed but runtime execution still expects an explicit `Universe` DataFrame.
- Drive-time units do not use network datasets; rows are ranked by straight-line distance.

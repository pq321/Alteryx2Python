# Distance Tool Semantics

`Distance` is implemented as a deterministic WKT baseline for official sample workflow conversion.

Supported behavior:

- Reads source and destination WKT fields from the same input row.
- Uses the average of all WKT coordinate pairs as each object's center.
- Computes straight-line haversine distance for Miles, Kilometers, Meters, and Feet outputs.
- Adds `DistanceMiles`, `DistanceKilometers`, `DistanceMeters`, or `DistanceFeet` when output distance is enabled.
- Adds `Direction` as an 8-point compass abbreviation and `DirectionDegrees` as a north-clockwise bearing when requested.
- Preserves all input rows and fields.

Limits:

- This is not a full spatial engine.
- Drive-time mode does not use network datasets; it emits a straight-line `DriveDistance*` baseline and leaves `DriveTimeMinutes` null.
- Inside-edge, nearest-object, line distance, polygon edge distance, and native Alteryx spatial object behavior are not implemented.

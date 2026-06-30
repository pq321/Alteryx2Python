# MapInput Tool

## Coverage

- Parses embedded Map Input fields and drawn rows from sample workflows.
- Emits an `Output` DataFrame with the configured fields.
- Converts embedded GeoJSON point and polygon values in `SpatialObj` to WKT strings.
- Handles selection-mode samples with nil rows as an empty DataFrame with configured columns.

## Deferred

- Reading external reference map files is not implemented.
- Selection-stack filtering against reference data is not implemented.
- Spatial object fidelity is limited to sample point/polygon WKT conversion.

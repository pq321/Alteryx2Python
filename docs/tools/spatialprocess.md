# SpatialProcess Tool Semantics

`SpatialProcess` is implemented as a deterministic WKT-oriented baseline for official sample workflows.

Supported behavior:

- Reads one `Input` anchor and emits one `Output` anchor.
- Requires both configured spatial object fields to exist.
- Preserves input rows and columns.
- Adds `SpatialObj_Process` using conservative action-specific selection:
  - `Cut1_From2` and other `*From2` actions use the second configured spatial field.
  - `Combine` and `Union` create a WKT-like `GEOMETRYCOLLECTION` when both fields are present.
  - Other actions fall back to the first configured spatial field.
- Honors `noEmpty=True` by removing rows with empty process output.

Known limits:

- This does not perform exact polygon difference, union, or intersection.
- Native Alteryx spatial object binary formats are not decoded.
- The baseline is intended to keep sample workflow topology executable while making spatial-processing assumptions explicit in runtime evidence.

# PolySplit

Baseline support splits WKT-like spatial text into point rows.

- Input anchor: `Input`
- Output anchor: `Output`
- Current behavior: reads the configured spatial field, emits `Split_SequenceNum`, `Split_SpatialObj`, and `Split_OriginalRecordID`.
- Limitation: non-point split modes retain the original spatial value as a conservative placeholder.

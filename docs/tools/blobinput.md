# BlobInput

Baseline support reads configured files into a `Blob` column.

- Input anchor: optional `Input`
- Output anchor: `Output`
- Current behavior: resolves the configured path or filename field, reads bytes, and optionally emits fixed-size blob chunks.

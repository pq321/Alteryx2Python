# BlobOutput

Baseline support records the intended blob write configuration without writing files.

- Input anchor: `Input`
- Output anchors: none
- Current behavior: validates the input frame, records filename/blob-field metadata, and marks `external_write_performed=false`.

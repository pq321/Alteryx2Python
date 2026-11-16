# BlobOutput

- Input anchor: `Input`
- Output anchors: none
- Writes actual bytes for fixed destinations and for per-row filename or path
  replacement. Relative paths resolve from the workflow directory.
- Run test cases with isolated output paths. Native output comparison and
  additional filename modes still require dedicated fixtures.

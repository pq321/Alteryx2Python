# BlobInput

Phase One and standalone Phase Two read configured files into a `Blob` column.

- Input anchor: optional `Input`
- Output anchor: `Output`
- A connected field may replace the entire path. That mode accepts an empty
  static filename, keeps incoming columns, and reads each selected file as bytes.
- The saved Stop With Error option controls inaccessible files. Saved chunk
  sizes are in KB and chunk output adds `BlobNumber`.

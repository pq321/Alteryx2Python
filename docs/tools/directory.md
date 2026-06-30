# Directory

Status: `L2_BASIC_IMPLEMENTATION`

Supported anchors:

- Output: `Output`

Implemented semantics:

- resolves relative directories against workflow `base_dir`
- supports `FileSpec`
- supports optional recursive enumeration via `IncludeSubDirs`
- emits file path, name, extension, size, and timestamp fields

Deferred semantics:

- exact Alteryx timestamp formatting and filesystem metadata parity
- sandbox policy beyond explicit local path resolution

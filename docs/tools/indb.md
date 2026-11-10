# In-DB tools

`alteryx2python.tools.indb` provides local implementations for the installed
In-DB catalog (`LockIn*`). Transformations use the same pandas semantics as the
canonical tools and preserve the original `LockIn...` tool type in execution
traces. `LockInInput`/`LockInOutput` (and stream/dynamic variants) require an
explicit local sqlite database (`connection`/`database`) and table or query;
remote connection strings and implicit credentials are rejected.

The module exports `IMPLEMENTATIONS`, `ANCHORS`, and `PARSERS` for registry
integration. `LockInTranspose` remains available for workflows containing the
removed catalog entry.

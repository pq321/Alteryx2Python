# Local external runtimes

`local_runtimes` provides bounded adapters for R, Runner, JupyterFlow, and
CustomSpark. They require explicit local executables/files and propagate real
subprocess/notebook failures. R bridges CSV files through `ALTERYX_INPUT` and
`ALTERYX_OUTPUT`; R exposes one read.Alteryx/write.Alteryx CSV bridge with a per-run null sentinel and timeout. JupyterFlow requires `nbclient` and a notebook writing a fresh output to the injected `ALTERYX_OUTPUT` path; `ALTERYX_INPUT` contains the input CSV. It cannot reuse an old output CSV.
CustomSpark uses a supplied session or local-mode pyspark. No Engine API,
licenses, credentials, or remote services are inferred.

Runner executes the canonical local Python graph, propagates runtime configuration, detects recursive inclusions and requires an explicit target when there are multiple terminal nodes. These CSV/local execution profiles do not certify native R types, arbitrary notebook integrations or Spark connector settings.

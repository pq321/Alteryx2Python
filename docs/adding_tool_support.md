# Add support for an Alteryx tool or configuration

Start with one runnable workflow and the tool ID that blocks migration. Record
the Designer version, engine, XML plugin ID, tool configuration, connections,
expected files and error behavior. Use small local fixtures with the same
configuration. Preserve the source workflow and its original XML.

## Locate the gap

```powershell
$py = '.venv/Scripts/python.exe'
& $py -m alteryx2python.cli inspect path/to/case.yxmd
& $py -m alteryx2python.cli support-map path/to/case.yxmd
& $py -m alteryx2python.cli readable path/to/case.yxmd --output reports/case.py
```

Use the node ID to locate its `GuiSettings`, `EngineSettings`, configuration
and named anchors. Check whether the failure happens in parsing, during
canonical execution, while collecting Designer evidence, or during standalone
compilation. A recognized plugin can still have an unsupported mode.

## Implement the observed behavior

1. Add or update the XML aliases and anchors in `alteryx2python/parser/tool_catalog.py`.
   Normalize the options in `parser/tool_parsers/` while keeping the raw
   configuration available. Cover the actual XML shape in a parser test.
2. Implement the observed configuration in `alteryx2python/tools/` and wire it
   into `tools/registry.py`. Identify unsupported options explicitly. Preserve
   row order, field declarations, nulls, and all output anchors.
3. Lower supported configuration in the relevant Phase Two generator module.
   Resolve settings at compile time and share small, audited data operations
   through the source linker. The delivered Python should import ordinary
   dependencies and run without the converter. Leave unsupported configurations
   as compiler blockers with the tool ID and reason.
4. For file-producing tools, put outputs in a fresh run directory. Preserve
   worksheet selectors during redirection. Test multiple groups and filename
   collisions when the output filename comes from data.

## Collect evidence and test

- Test a normal case, an empty input, relevant null/duplicate/type cases, and
  an invalid or unsupported option. Check named inputs and outputs, including
  disconnected output anchors. Create CSV/XLSX fixtures inside the test so a
  developer can run them without the Designer sample installation.
- Capture Designer outputs and diagnostics independently. Use the installed
  Designer to capture tool boundaries and actual deliverable files. Read the
  workflow [parity guide](tools/phase_one_parity.md) for probes, disabled
  containers, macros, AMP export and attestation. A tool excluded from automatic
  capture needs a bounded native fixture and independently recorded outputs.
- Compare both Python phases using identical inputs, options and run date.
  Run the generated delivery file in a separate process and compare artifacts.
  Use byte comparison for deterministic text and `compare --mode xlsx` for
  workbook sheet order, cells and formulas. Test layout and style separately
  if those form part of the acceptance criteria.
- Preserve errors. A failed execution should return a nonzero exit code and
  identify the tool or input that failed. A deliberately changed logging
  destination is verified through its documented structured fields and lifecycle.
- Run the focused parser, tool, compiler and end-to-end tests first, then the
  full relevant suite. Record which configurations ran in Designer, which
  ran through both Python phases, and which still require an installation,
  external system or private fixture.

See the [Designer delivery demo](designer_delivery_demo.md) for the full
evidence chain and the [compiler contract](../.trellis/spec/backend/readable-python.md)
for standalone generation and verification requirements.

# Visual Workflow Editor (drag & drop -> .yxmd + native Python)

A zero-dependency web frontend (vanilla JS + SVG) served by a stdlib Python
server. Draw a workflow on your own panel: drag tools from the palette,
connect their anchors, configure each node, then Save/Compile to produce
both a real Alteryx .yxmd document and a standalone native-Python (pandas)
script - no alteryx2python imports required by the generated code.

## Run

    uv run python webapp/server.py --port 18080
    # open http://127.0.0.1:18080

## Editor capabilities

- Palette grouped by category (In/Out, Preparation, Transform, Join, Parse)
  with 20 tools; drag onto the canvas (or double-click a palette item).
- Anchor-aware connections: drag from an output dot to an input dot;
  Filter exposes True/False outputs, Join exposes Left/Right inputs - the
  anchor names match the real Alteryx tool metadata.
- Per-node configuration panel: TextInput column/row grid, Formula
  expression lists, Summarize action lists, Select field pickers, etc.
- Toolbar: Save/Compile (shows YXMD + Python tabs, download buttons), Run
  (executes the canonical runtime and renders the result table), Clear.
- Keyboard: Delete removes the selected node; double-click an edge to
  delete it.

## Compile pipeline

    editor graph JSON
      -> webapp/graph_compiler.py  -> WorkflowBuilder -> official .yxmd XML
      -> webapp/standalone_gen.py  -> self-contained pandas script

The .yxmd output uses the same official Configuration shapes as the
equivalence suite, so a drawn workflow loads directly in real Designer.
The standalone script translates the supported tool subset into plain
pandas (groupby/agg, merge, melt, pivot_table, str.extract, ...), infers
TextInput column types statically, and formats CSV output the way the
native writer does (integral doubles without '.0', nulls as empty cells).

Expression subset for Filter/Formula: '[Field]' references, comparisons,
AND/OR/NOT; '[Row-1:Field]' works in Multi-Row Formula via a generated
shift(1) loop. Anything outside the subset is reported in 'unsupported'
and shown as a warning instead of being silently miscompiled.

## Guarantees

`tests/test_webapp/test_editor_backend.py` proves that for the demo graph
the compiled standalone script and the canonical alteryx2python runtime
produce byte-identical CSV output (values and native formatting).

## API

- `GET  /api/tools` - palette metadata (types, anchors, defaults)
- `POST /api/compile` - `{name, nodes, edges}` -> `{yxmd, python, unsupported}`
- `POST /api/run`    - compile + execute through the runtime -> result rows

Learning-purpose reverse engineering only; no Alteryx code is copied.

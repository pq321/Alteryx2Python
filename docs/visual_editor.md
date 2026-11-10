# Visual Workflow Editor

The editor uses a strict TypeScript frontend and the existing Python runtime.
It has no frontend runtime dependencies. TypeScript is the only frontend build
dependency. The compiled ES modules under `webapp/static/dist/` are checked in so
the Python server can also run without a Node installation.

## Run

```powershell
uv run python webapp/server.py --port 18081
# Open http://127.0.0.1:18081
```

For frontend development:

```powershell
cd webapp
npm ci
npm run typecheck
npm test
npm run dev
```

`npm run dev` watches TypeScript sources. Refresh the browser after changes.
`npm run build` updates the checked-in browser modules. No bundler, framework,
or separate frontend server is required.

## Inputs And Editing

- Text Input is an editable cell grid with editable column headings, add/remove
  rows and columns, and rectangular paste from Excel or other tabular sources.
  Tabs separate pasted cells; quoted tabs/newlines and commas remain cell data.
  Enter moves to the next row; Tab at the final cell adds a row; Shift+Enter
  inserts a newline. The expand control widens the configuration panel.
- Drop CSV, TSV, TXT, or XLSX files onto the canvas to create real Input File
  nodes. The file picker supports multiple files. Dropping onto a file node's
  upload area replaces its file. Files are limited to 20 MiB each.
- CSV import handles quoted cells, BOMs, UTF-8, UTF-16 with a BOM, GB18030, and
  common delimiters. Blank/duplicate headings and ragged records are rejected.
  XLSX inputs expose a worksheet selector. Legacy XLS is not offered.
- Uploads and selected worksheets are normalized to UTF-8 CSV under
  `webapp/.uploads/` (gitignored). Node previews show the first 100 rows;
  execution reads the entire normalized file. Original uploads are retained
  for worksheet changes. Imported files are snapshots, not live file watchers.
- Workflow JSON and generated Python/XML reference these local CSV paths.
  Reimport source files when moving the workflow to another computer or after
  removing its upload directory. Uploads persist between server restarts.

## Workflow Controls

The palette contains 21 editor-supported tools, grouped and searchable in
Chinese or English. Click a tool to append it to the selected node when an
input/output connection is possible; drag to position a node independently.

The canvas supports node dragging, background panning, zoom, fit, and either
dragging or clicking output/input ports to connect. Duplicate connections,
cycles, occupied single-input ports, and missing anchors are rejected.
Connections can be removed in node configuration or by double-clicking them.
Delete removes the selected node or connection. Configuration and results
panels can be resized; the tool palette collapses and becomes a drawer on
small screens. Closing configuration does not delete the node.

Field selectors use upstream schema suggestions. Formula, sort, summarize,
select, transpose and other supported tools expose their actual configurations.
Workflow JSON can be opened/downloaded, and the local browser draft is saved
automatically. Undo/redo preserves graph and configuration edits. Replacing a
nonempty workflow asks for confirmation and can be undone.

## Execution And Export

- Run executes every node through the canonical Python runtime, including
  workflows without an Output Data sink. Each node/anchor has a result preview.
- Result previews show at most 500 rows; CSV downloads contain all output rows.
  Filter's True/False and Unique's Unique/Duplicates are separate outputs.
- Preview runs isolate output sinks in a temporary directory. They do not write
  configured output paths. Use CSV download for results; exported scripts write
  their configured output paths when executed.
- Generate Code produces Designer-format XML and a standalone pandas script.
  Python export respects file inputs, branch anchors, Select's includeUnknown,
  Record ID field names, and UTF-8 output. Unsupported translations are visible
  and block Python download. XML can still be downloaded.
- Editing marks old results/code stale and disables their download until the
  relevant workflow version is run/compiled again. Compilation and execution
  errors remain visible instead of being presented as successful results.

The editor is a supported subset, not a promise of complete Alteryx equivalence.
The standalone generator retains its existing expression/operation limits.
Python/runtime agreement tests do not constitute native Alteryx certification
or completed user acceptance.

## API

- `GET /api/tools`: tool types, anchors, defaults.
- `POST /api/import`: `{name, content: base64, sheet?}`, or
  `{sourceFile, name, sheet}` to change an existing uploaded workbook's sheet.
  Returns local file paths, fields, first 100 rows, total row count and sheets.
- `POST /api/compile`: `{name, nodes, edges}` to Python/XML plus limitations.
- `POST /api/run`: the same graph, compiled artifacts and per-node/anchor
  `previews` with columns, first 500 rows, rowCount and complete CSV data.

## Verification

```powershell
.venv/Scripts/python.exe -m pytest tests/test_webapp -q --no-cov
npm --prefix webapp test
```

Backend regressions cover import formats, quoted cells, workbook selection,
preview limits, isolated sinks, UTF-8 output, Record ID configuration, branch
routing, Select/Unique export and graph validation. Node's built-in test runner
checks clipboard parsing, table expansion, workflow import, field inference
and connection validation. Browser smoke checks cover table paste, file drop,
execution, downloads, stale results, autosave and desktop/mobile layouts.
Run the smoke script with an existing Playwright installation (supplied via
the PLAYWRIGHT_MODULE environment variable), optionally CHROMIUM_PATH for an
existing browser executable, and EDITOR_URL for the running editor URL:

    node webapp/tests/browser-smoke.mjs

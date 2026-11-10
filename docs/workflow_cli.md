# Workflow CLI: construction, configuration, Python execution and evidence

Local learning and practice. Reviewed on 2026-11-10 against the installed Designer
2025.1.2.165 and the pinned official inventory. The CLI now handles general graphs;
the ten presets are convenience examples. Generating valid XML, executing Python,
and demonstrating native equivalence are separate acceptance stages.

## Commands

| Command | Purpose |
| --- | --- |
| generate-workflow --preset P --output w.yxmd | Generate one of ten deterministic examples |
| generate-workflow --spec graph.json --output w.yxmd --python-output w.py | Generate a catalog-backed graph and its runnable Python in one invocation |
| workflow-export w.yxmd --output graph.json | Export editable nodes/edges plus source XML |
| node-template w.yxmd --node 3 --new-id 4 --output node.json | Extract a native node, including unknown configuration/GUI/engine properties |
| workflow-edit w.yxmd --add-node node.json --connect "3:Output=4:Input" --output edited.yxmd | Add nodes and connections; also supports --remove-node and --disconnect |
| validate-workflow w.yxmd [--require-executable] | Validate references, duplicate IDs/connections, known ports and data cycles; report missing execution adapters |
| tools [--tool NAME] [--output tools.json] | Enumerate all official identifiers, implementation profiles and declared anchors |
| questions app.yxwz | List native question names/IDs, defaults, choices and numeric bounds |
| configure-workflow app.yxwz --answers answers.json --output resolved.yxmd | Bind answers and compile Actions into a data graph |
| configure-workflow app.yxwz --answers answers.json --defaults-only --output app-copy.yxwz | Keep the native interface/Actions and change question defaults |
| generate w.yxmd --output w.py [--answers answers.json] | Preserve source XML/full IR, snapshot local macro dependencies, generate runnable Python |
| run-python w.yxmd --output-dir results [--answers answers.json] | Execute the full graph and export typed per-node results |
| run w.yxmd --target-node ID [--answers answers.json] | Execute a target and its ancestors, applying question defaults |
| run w.yxwz --target-node ID --data-slice | Explicit migration-slice mode which skips app configuration; not full-app acceptance |
| run-native w.yxmd [--watch-file output.csv] | Run the documented headless EngineCmd backend |
| equivalence w.yxmd [--oracle oracle.csv] | Final CSV comparison, explicitly limited to file values |
| equivalence w.yxmd --per-node --output-dir evidence [--engine PATH] | Typed native/Python node input/output comparison |
| equivalence-suite --out-dir D | Generate and compare all requested presets |
| proof-suite --cases cases.json --out-dir D [--engine PATH] | Per-tool/configuration case ledger, with per-node evidence and explicit blocked cases |

All commands emit JSON and accept --log FILE. New evidence/result directories must
be fresh. Blocked or incomplete proof suites return exit 2; mismatches return 1.
A suite containing only blocked native attempts never returns success.

## One-command generation, then direct Python execution

Run from the repository environment:

```powershell
Set-Location E:\Automation\Alteryx2Python
uv sync --extra local --extra parity --extra test --extra nlp --extra notebooks
.\.venv\Scripts\python.exe -m alteryx2python.cli generate-workflow --spec examples\cli\branch.json --output reports\demo\branch.yxmd --python-output reports\demo\branch.py
.\.venv\Scripts\python.exe reports\demo\branch.py --output-dir reports\demo\python-results
```

Generated Python has build_workflow(), run_workflow(), and an executable main
entry. It requires this project's runtime/dependencies; it is not a standard-library-only
transpilation. With --output-dir it exports typed per-node JSON/CSV and images.
Without that option it runs the workflow and prints results as JSON.

Source XML, node metadata, anchor definitions, dependency lists, warnings and
workflow metadata are preserved. Local custom macro XML is embedded recursively.
Tests delete both the source workflow and nested macro files before running the
generated code. External data, interpreters, models and services remain real
dependencies. Unresolved macro references are recorded, not fabricated.

## General graph schema

See [branch.json](../examples/cli/branch.json) for a runnable example.

```json
{
  "kind": "yxmd",
  "nodes": [
    {
      "node_id": "1",
      "tool_type": "TextInput",
      "configuration_xml": "<Fields><Field name=\"x\"/></Fields><Data><r><c>3</c></r></Data>"
    },
    {
      "node_id": "2",
      "tool_type": "Filter",
      "configuration_xml": "<Mode>Custom</Mode><Expression>[x] &gt; 1</Expression>"
    }
  ],
  "edges": [
    {"source": "1", "source_anchor": "Output", "target": "2", "target_anchor": "Input"}
  ]
}
```

ToolID values are positive integer strings. A node can specify:

- tool_type or exact plugin_id; catalog engine bindings are used when available.
- configuration_xml, either child elements or a Configuration wrapper.
- template_xml to preserve an extracted native node.
- macro_path for a local .yxmc reference.
- input_anchors/output_anchors for custom/SDK/macro port declarations.
- engine_dll/engine_entry for an explicit external plugin binding.
- source_dir for an extracted node's original resource directory.

Workflow kind is yxmd, yxmc or yxwz. properties_xml can supply native Properties,
including RuntimeProperties/Questions/Actions. source_xml preserves unknown root
properties. base_dir and source_dir preserve known relative file/macro references
when moving a document; they are resolved to absolute local references. Resource
packaging for transfer to another machine is a separate step.

Unknown tools need explicit bindings or a native template. No generic
AlteryxBasePluginsEngine entry is guessed for every tool. Imported/SDK templates
may lack complete port metadata; their unknown ports still require native
validation. XML preservation is structural, not byte-for-byte whitespace/comment
preservation. Unrelated properties, Question trees and engine settings survive edits.

To append a tool entirely from the CLI:

```powershell
.\.venv\Scripts\python.exe -m alteryx2python.cli node-template reports\demo\branch.yxmd --node 3 --new-id 4 --output reports\demo\node4.json
.\.venv\Scripts\python.exe -m alteryx2python.cli workflow-edit reports\demo\branch.yxmd --add-node reports\demo\node4.json --connect "3:Output=4:Input" --output reports\demo\extended.yxmd
```

This example reuses a Formula template. For another tool, extract its configured
node from an installed official sample or a workflow you saved in Designer.

## Questions, configuration tools and macros

The configuration stage reads actual native RuntimeProperties/Questions and
Actions. Annotation text is not used as the full app parameter contract.
Answers are a JSON object keyed by question name or question ToolID.

```powershell
.\.venv\Scripts\python.exe -m alteryx2python.cli questions examples\cli\parameter-app.yxwz
.\.venv\Scripts\python.exe -m alteryx2python.cli run-python examples\cli\parameter-app.yxwz --answers examples\cli\answers.json --output-dir reports\demo\app-results
.\.venv\Scripts\python.exe -m alteryx2python.cli configure-workflow examples\cli\parameter-app.yxwz --answers examples\cli\answers.json --output reports\demo\resolved.yxmd
```

Default compilation applies Actions once and removes the interface/control graph
from the emitted data workflow. It does not leave replacement Actions to run a
second time. --defaults-only instead preserves the native app for Designer.
Neither mode modifies the source file.

Supported local question profiles include text, booleans/radio groups, bounded
numbers, dates, manual choices/list selections and file/folder values. Supported
Actions include UpdateValue, replacement, UpdateValueFormula, conditional
True/False groups, validation Error, inner UpdateRawXml, and same-format
UpdateInput/UpdateOutput file paths. Expressions use the existing Alteryx
expression interpreter, not Python eval.

Macro profiles implemented:

- Standard: named MacroInput/MacroOutput, caller Value answers, nested local macros.
- Batch: one ControlParam, one reconfigured graph run per control record, output
  union by name/position or matching layouts. Empty controls use an explicitly
  declared boundary schema; otherwise the case is blocked.
- Iterative: a configured feedback input/output, iteration limit and empty-feedback
  termination, with a local maximum-iteration budget. The demonstrated profile
  accumulates non-feedback outputs by name.

Ready examples: [standard](../examples/cli/standard-macro.yxmd),
[batch](../examples/cli/batch-macro.yxmd),
[iterative](../examples/cli/iterative-macro.yxmd), and their .yxmc dependencies.
The standard example returns y=6,15; batch returns y=6,15,8,20; iterative returns x=0,0.

Field-map UI semantics, multiple simultaneous batch controls, all iterative
schema/constant modes, dynamically populated selections, Map/Tree geometry,
DCM credentials and specialized Action types are not universally implemented.
Unsupported configuration adapters must remain visible; passing the shown
profiles does not certify every configuration of these tools.

Official behavior references:
[Action](https://help.alteryx.com/designer/current/en/tools/interface-tools/action-tool.html),
[Control Parameter](https://help.alteryx.com/designer/current/en/tools/interface-tools/control-parameter-tool.html),
[Drop Down](https://help.alteryx.com/designer/current/en/tools/interface-tools/drop-down-tool.html).

## Equivalence evidence

The default contract is both fail, regardless of exception wording, or both
succeed with equal results. Implementation/dependency/license failures are
blocked, not legitimate matching workflow errors.

The legacy CSV route is explicitly final-csv-only. It freezes the oracle before
Python runs, isolates Python sinks, retains Unicode/header order/whitespace,
checks row counts and preserves NULL versus empty in typed comparisons.
CSV itself loses original null/empty/type distinctions, so matching CSV cannot
prove every tool or intermediate node.

--per-node reuses native YXDB probes and typed snapshots. It compares all exposed
node anchors including empty/disconnected branches. File sinks have no native
outgoing stream; compare their input records, not a fabricated output anchor.
Original sink files are redirected into evidence directories. Source, runtime,
native output and macro dependency hashes prevent stale evidence reuse.
Successful stream comparisons do not certify report rendering, opaque native
model formats or remote side effects. Macro boundary outputs are checked;
native inner-macro checkpoints require separate instrumentation.

```powershell
.\.venv\Scripts\python.exe -m alteryx2python.cli equivalence reports\demo\branch.yxmd --per-node --output-dir reports\demo\native-proof
.\.venv\Scripts\python.exe -m alteryx2python.cli proof-suite --cases examples\cli\proof-cases.json --out-dir reports\demo\macro-proof
```

The case manifest names each workflow and tools actually present in it.
The proof ledger associates acceptance with those configurations. It cannot
attribute a passing workflow to an absent tool, and never labels all tools
universally equivalent. Missing tools/cases remain unverified.

For manually run Designer workflows, retain the independent
[prepare/attest/collect and human review routes](tools/catalog.md).
A configured graph produced by this Python configuration compiler can validate
its data processing against native execution; it does not independently prove
that native Designer applied every Question/Action identically.

## Native execution and audit corrections

Only the documented EngineCmd backend is used by auto. On Windows it starts
without creating a console window. The designer-cli selector now returns blocked:
opening a file in AlteryxGui, even from Task Scheduler, is not a guaranteed
headless execution contract and can affect the existing single-instance window.
The CLI creates no scheduled tasks and does not manipulate AppData.

EngineCmd exit codes 0/1 are success/warnings; errors, missing fresh outputs,
timeouts and licensing are distinguished. Existing oracle files are never
deleted. Diagnostics come from the bounded process's stdout/stderr, not an
unrelated shared GUI log.
[Official command-line/license requirements](https://help.alteryx.com/designer/current/en/workflows/run-workflows-via-command-line.html).

Audit repairs include: blocked-suite exit status, stale/oracle overwrite safety,
row counts/whitespace/NULL/Unicode handling, native binding names, quoted XML
attributes, relative resource relocation, complete IR serialization, executable
generated scripts and embedded custom macro configurations. Formula's previous
catalog entry came from a commented EngineSettings element; the active installed
manifest and official sample use AlteryxBasePluginsEngine.dll / AlteryxFormula.
RegEx and CrossTab require AlteryxRegEx and AlteryxCrossTab.

The 2026-11-10 acceptance artifacts are under reports/cli-acceptance/2026-11-10.
Thirteen CLI invocations and direct generated-Python execution were exercised.
Three macro proof cases preserve actual EngineCmd license failures; they are
blocked, not native-equivalence passes. See the checked-in
[acceptance report](tools/evidence/2026-11-10-cli/README.md).

All 321 unique official IDs remain mapped; 226 category entries have executable
profiles and 97 still require resources or adapters. Full all-tool lossless
semantic conversion is not established. The CLI construction/configuration and
evidence paths are implemented; native coverage grows through independent cases.


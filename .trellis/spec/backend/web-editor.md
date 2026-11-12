# Web Editor Contract

## 1. Scope / Trigger

Applies to webapp graph storage, native XML import/configuration, tool exposure,
runtime invocation, standalone export and TypeScript clients.

## 2. Signatures

- GET /api/tools returns tools, unavailable and workflow configuration metadata.
- POST /api/workflow/import accepts name, xml and optional sourcePath.
- POST /api/macros/import accepts name, xml and files with relative names/xml.
- POST /api/compile and /api/run accept the same editable graph document.
- ReadablePythonGenerator.generate(workflow, answers=None, constants=None,
  parameter_mode='dynamic', delivery_profile=None) is the sole native compiler.

## 3. Contracts

Graph nodes/edges retain unknown JSON fields, per-node ports and toolDefinitions.
workflowXml preserves native Properties, configurations, EngineSettings,
container ownership and connection attributes. Optional propertiesXml,
runtimePropertiesXml, eventsXml and constantsXml configure those sections.
Editors must share one effective XML source and detect stale drafts; applying
one section must not silently overwrite changes made through another editor.

Runtime settings include answers/constants, delivery_profile, allowed_commands,
input_dir, event_working_dir, command_working_dir, command_timeout and
allow_external_runtimes. Draft delivery is the default. Credentials belong in
SMTP_* environment variables. Arbitrary commands are never implicitly allowed.

Compile returns native source/manifest only on success, otherwise XML plus typed
blockers. A Phase Two blocker does not prohibit an independently implemented
runtime execution. Run returns per-anchor previews, stdout, diagnostics, warnings
and downloadable artifacts. Sink redirection applies to event attachments too.

Dynamic exports retain supported named Python parameters; specialized exports
explicitly freeze answers before compilation. The manifest records the choice.
UI language is stored separately and never translates user data, XML or code.

## 4. Validation And Error Matrix

- Malformed XML, invalid root/graph/ports/options: invalid configuration.
- Registered unavailable or metadata-only adapter: explicit runtime blocker.
- Unimplemented native template/configuration: Phase Two blocker, no Python.
- Command outside explicit allowlist: permission denied.
- Missing macro dependency or external interpreter: explicit dependency blocker.
- Unsaved advanced edits: client prevents execution/export until resolved.
- Macro upload paths escaping the bundle: rejected before writing.

## 5. Good / Base / Bad Cases

Good: import a nested macro app, edit answers/events/constants, save/reload,
execute, export native source, and compare results with the canonical path.
Base: runtime works while native export reports a specific unsupported template.
Bad: metadata passthrough advertised as execution, or failed compilation returning
a legacy fallback script with different semantics.

## 6. Tests Required

Exercise real HTTP and browser paths: table paste and imported TextInput grids,
file drop, all workflow XML sections, connected custom macro restoration,
cross-editor conflict handling, dynamic/specialized export, current event
attachments, typed failures, artifact downloads and persisted language switches.
Check desktop/mobile overflow. Preserve native equivalence as a separate gate.

## 7. Wrong Versus Correct

Wrong: add a second editor-specific expression compiler or claim all registered
tools are executable.
Correct: delegate to canonical native templates; expose executable adapters with
complete configuration access and explicit configuration-specific blockers.

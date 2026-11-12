# Engine Component Coverage (beyond tools)

This is a configuration-specific implementation inventory, not proof that every
Alteryx component or configuration has an executable mapping. Runtime execution,
native source compilation and native Alteryx equivalence are separate gates.
See [current coverage evidence](component_mapping_status.md).

| Component | Python mapping | Status |
| --- | --- | --- |
| Workflow Events | Native Before/After/AfterError/AfterNoError/Disabled and warning aliases; both command argument spellings; allowlisted commands; explicit email drafts/SMTP, including attachments | runtime and Phase Two; macro-local Phase Two events remain blocked |
| Official built-in macros | local_macros.py: 14 native pandas implementations (CountRecords, SelectRecords, WeightedAvg, Imputation, RandomRecords, CreateSamples, MultiFieldBinning, Oversample, FieldSummary, Base64Encoder, JSONBuild, Spearman, Frequency, Contingency) | implemented |
| Generic + nested macros | macro_engine.py loads any .yxmc, binds MacroInput/MacroOutput anchors, applies interface answers, and executes the inner graph; nesting recurses through the same registry route (test: caller -> outer.yxmc -> CountRecords.yxmc) | implemented |
| Run Command tool | tools/runcommand.py with allow-listed subprocess execution | implemented |
| Python Tool (Jupyter) | Saved code/notebooks lower through the same AST boundary compiler for runtime and standalone source; numbered IO, metadata and constants; Web execution captures stdout | supported vendor API subset; unknown APIs block conversion |
| Action tool (analytic app updates) | Runtime binds Questions/Actions before graph execution. Dynamic Phase Two parameters support recognized bindings. Explicit specialized export applies fixed answers, including conditional/formula/raw XML, selection and deletion Actions, before compilation | DynamicAction and unverified value adapters remain explicit blockers |
| Global / engine variables | engine_variables.py: the ten engine constants harvested from the native DLL string tables (WorkflowDirectory, WorkflowFileName, TempFilePath, ModuleDirectory, IterationNumber, OS, Version, Type, ReportFont, GuiInteraction) as [Engine.X] expression constants | implemented |
| User variables / question substitution | '%Question.<Name>%' percent tokens in any tool configuration string are resolved from bound answers before execution (executor pipeline + macro bodies); '%temp%' and '%Engine.X%' tokens resolve through the same layer | implemented |

SMTP is never a successful no-op: drafts require html-draft-v1, sending requires
html-smtp-v1 and valid transport settings. Native encrypted credentials and DCM
connections require a separate credential adapter; SMTP_PASSWORD is read from
the environment. Event attachments referencing redirected workflow sinks bind
to their current output files, while external attachments retain input paths.

Remaining gaps include batch/iterative macro Phase Two compilation, macro-local
events, data-driven DynamicAction, Map/Tree value adapters, advanced native
reports, proprietary services/formats and missing configured fixtures. The Web
App exposes executable runtime adapters and preserves complete XML settings;
unsupported execution/native export is reported rather than silently skipped.

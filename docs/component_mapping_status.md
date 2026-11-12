# Component Mapping Status

As of November 12, 2026. This is an in-progress framework expansion, not complete
Alteryx engine coverage. The official list is the repository's November 9 snapshot;
the web reference could not be refreshed in this session.

## Current Evidence

- Full suite: 1,254 passed, 86.21% coverage; seven warnings (including the official
  Python sample's intentional warning and dependency/numerical warnings).
- Connected benchmark: all 38 outer-node checkpoints and eight actual artifacts
  match between canonical Python and generated Python. The delivered source also
  executes separately from the instrumented build.
- Installed official Python Tool sample: its six saved programs compile and run
  through both paths, including numbered outputs and metadata writes.
- SMTP: SSL, STARTTLS, explicit plain, authentication, attachments, recipient
  refusal and generated-source transport are verified with mocked connections.
  No real mail was sent.
- Inventory: 293 workflow/app/macro sources, 323 official rows / 321 unique XML
  identifiers; 89 rows have at least one configuration that compiles. This is
  non-executing evidence. Thirty-four official rows have connected-benchmark
  Python differential evidence, not native certification.
- Native Alteryx equivalence remains unverified. No new native engine run was
  attempted in this expansion.
- Web: TypeScript typecheck/build, 13 frontend unit tests and both real-browser
  suites pass. Desktop/mobile checks cover 1440x960, 1024x768, 390x844 and
  390x568. The palette exposes 224 executable runtime entries and separately
  reports 121 unavailable or metadata-only entries.

Current generated evidence (repository-relative):

- reports/readable-dev/web-components-2026-11-12-final-tests.json
- reports/readable-dev/web-components-2026-11-12-final-verified/acceptance.json
- reports/readable-dev/web-components-2026-11-12-final-verified/readable.py
- reports/readable-dev/web-components-2026-11-12-audit/coverage.json
- reports/readable-dev/web-components-2026-11-12-audit/missing-components.md

## Framework Changes

| Component | Implemented contract | Remaining boundary |
| --- | --- | --- |
| Workflow events | Native singular timing names, Disabled and warning aliases; both command argument spellings; batch files, working directories, allowlist; plain-body email drafts/SMTP and attachment relocation | Macro-local Phase Two events and DCM credential adapters |
| Static/nested macros | Recursive expansion, embedded source preservation, local variables, output ownership, nested containers | Batch/iterative Phase Two, unavailable macro packages and vendor-specific side effects |
| Python Tool | Saved code/notebook, input/output boundaries, metadata, constant APIs | Unmapped vendor APIs, global/nonlocal state, nested writes and package installation |
| User/Global variables | Saved declarations, percent tokens, expressions, root runtime and compile-time overrides, nested scopes; dynamic Question references use current parameters | Compile-time variable specialization is explicit; Engine values describe Python |
| Questions and Actions | Dynamic named parameters for supported operands, question references/tokens, file paths, Text Input cells and container enablement. Specialized export applies fixed conditional/formula/raw-XML/selection/deletion Actions before native lowering | DynamicAction, unverified value adapters and schemas without deterministic templates |
| Wait | Explicit WaitASecond/WaitSeconds duration and copied frame | Arbitrary external wait macro semantics need source |
| Reports and email | Basic HTML table/text/layout/render, drafts and explicit SMTP | Native report formats, advanced layouts and every Email setting |
| Source specialization | Audited frame boundaries and read-only helper configuration become ordinary arguments/operations | Mutable/aliased configuration blocks compilation |
| Web App | Registry-derived executable palette, lossless XML workflow/config editing, macro bundles, runtime settings, canonical Phase Two export, execution logs/artifacts and persistent Chinese/English UI | Runtime registration is not proof of Phase Two compilability or native equivalence |

## Web Integration Follow-up

The old editor-only standalone generator is no longer used by the Web API.
Compile responses declare compiled/blocked Phase Two status, include the native
manifest on success and preserve XML export when native lowering is blocked.
Runtime-capable workflows may still execute when their Phase Two configuration
is unavailable. The default delivery profile creates drafts; SMTP sending and
external commands require explicit configuration. No real mail is sent in tests.

Native event field names were checked against the installed
AlteryxDocument.Events.EventBase, EventRunCmd and EventSendMail implementations.
This local schema check does not establish native execution equivalence.

Python Tool metadata writes bypass unsupported dtype inference when an explicit
type is supplied, preserve inherited field source/description unless overridden,
and apply the output type's storage width. Both runtime and native compilation
have regression coverage for these boundaries.

## Outstanding Coverage

The inventory retains all 323 official rows. Registration of every row is not
proof of an executable native-Python mapping.

- 96 rows require an external adapter, service, model, licensed dataset or SDK.
  Examples include cloud connectors, Calgary/address datasets and hosted AI tools.
- 85 implemented-list rows have no configured fixture in the supplied corpus.
- 53 rows have supplied fixtures that do not compile as isolated native probes.
  This includes interface nodes that require grouped bindings as well as real
  gaps: advanced reporting, dynamic expression tools, media/model runtimes and
  unsupported source specialization.

The report lists each XML identifier and blocking reason. The active task remains
in progress. Completing all mappings requires real configuration fixtures,
additional deterministic templates/adapters and independent native evidence;
placeholder registration or agent interpretation cannot satisfy that requirement.

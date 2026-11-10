# CLI acceptance, 2026-11-10

The original preset CLI was not complete. This continuation implemented general
graph construction/editing, preserved native templates, question/Action binding,
parameterized/batch/iterative macro profiles and directly executable Python with
embedded local macro configurations.

## Measured results

| Evidence | Result |
| --- | --- |
| Full pytest | 649 passed, 4 dependency/numerical warnings |
| Coverage | 84.12%, 80% required |
| CLI acceptance sequence | 13 invocations checked, plus direct generated-script execution |
| Python workflow cases | Branch, raw parameter app, compiled app, standard macro, batch macro, iterative macro all produced checked values |
| New native macro proof cases | 3 blocked by actual EngineCmd licensing errors; 0 native matches claimed |
| Existing native fixture replay | Independently captured Designer YXDB probes still match through the node-proof path; this is offline replay, not a new native execution |
| Refreshed official inventory | 323 category rows / 321 unique IDs; no added/removed IDs since previous snapshot |
| Runtime coverage scope | 226 executable category profiles; 97 resource/adapter entries remain unresolved |

[acceptance.json](acceptance.json) records commands and source hashes.
[verification.json](verification.json) records the tested runtime hash and coverage.
[verification-tests.txt](verification-tests.txt) retains the full test output.
[proof-ledger.json](native-proof/proof-ledger.json) attributes each new macro case.
The per-case directories preserve native stdout/stderr, engine/output hashes,
instrumented XML, Python node capture and blocked reports.

Native EngineCmd 2025.1.2.165 reported:

> The Feature "API or FlowChartMode" is not licensed.

No Designer GUI launch, Task Scheduler command or AppData manipulation was used
by this acceptance sequence. The undocumented designer-cli selector is disabled
for guaranteed-background operation; auto uses EngineCmd only.

## Important repaired defects

- Blocked-only suites previously could return success.
- CSV comparison could hide row-count, whitespace, null/empty and Unicode differences.
- Original/native oracle files could be reused or overwritten by Python writes.
- Generated code dropped IR metadata/anchors and had no executable entry point.
- Question annotations were used instead of real RuntimeProperties definitions.
- Configuration output could retain already-applied replacement Actions.
- Macros rejected caller question values and batch/iterative configuration.
- Formula's catalog binding came from commented XML rather than the active engine
  entry; RegEx/CrossTab preset entry names were also incorrect.
- XML quoted attributes and relative resource relocation required corrections.

## Proof limits

Construction, Python execution and native semantic evidence remain separate.
The new macro examples are Python-validated local profiles with native attempts
blocked by licensing. They do not prove all native field maps, UI behaviors,
Action variants, iteration modes, model formats or side effects.
Final CSV equality is explicitly weaker than typed node equality. Boundary
checks do not automatically certify internal native macro checkpoints.

A passing finite case applies to its configuration, inputs and runtime version.
All-tool/all-input lossless conversion is not established. Use the complete
[CLI guide](../../../workflow_cli.md) and [tool catalog](../../catalog.md).
Archived instrumented XML contains paths bound to the original evidence folder;
create a fresh evidence directory for another native run.

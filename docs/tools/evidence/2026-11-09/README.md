# Observed native differential evidence

This is the historical strict-profile report. The user's subsequently clarified
default accepts equal successful results or failure on both sides without equal
exception text. See [the behavioral update](behavioral-update/README.md) for the
current 6-workflow, 30-check results and current mapping scope in [the catalog](../../catalog.md).

Original-engine Designer **2025.1.2.165**, local synthetic workflows, 2026-11-09.
These are actual Designer GUI outputs; Engine API execution was separately
attempted and returned an explicit license failure. No native result was generated
by Python. See [summary.json](summary.json) for workflow/fixture hashes and counts.

| Native run | Data checks | Values/order | Strict verdict |
| --- | --- | --- | --- |
| Branch/duplicates/Unicode | 7 | 7 match | incomplete |
| Many-to-many Join | 7 | 7 match | incomplete |
| Empty branch | 7 | 7 match | incomplete |
| Null versus Formula empty string | 3 | 3 match | incomplete |
| Missing field | Partial execution captured | Error messages differ | incomplete |
| Engine command | No native output | API feature not licensed | blocked |

The **24 matching data checks** cover node inputs as well as outputs. They do not
establish full schema/diagnostic equivalence. The checked-in YXDB fixtures are
native node outputs from the first and second runs, suitable for offline regression.

The failing Filter node demonstrates a diagnostic-text difference (not a failure
under the subsequently clarified default behavioral contract):

- Designer: `Parse Error at char(1): Unknown variable "missing_field"`.
- Python: `KeyError` with message `'missing_field'`.

Both execute the source before failing the Filter; missing downstream native
outputs remain visible. Native per-node diagnostics are not machine-certified by
the current collector. Raw observed Designer message rows are retained alongside
full native and Python snapshots; neither is silently normalized into a pass.

Verification: **525 tests passed**, **85.88%** total coverage (80% required).
Independent Python review prompted explicit unknown-diagnostic gates. A reviewer
suggested treating `null="False"` as empty string; actual native YXDB contradicted
that assumption, so the behavior follows the runtime evidence instead.

The broader requirement remains open: 142 official category rows have no exact
catalog mapping, Python field metadata needs propagation, and structured native
diagnostics, add-ons, macros, connectors, UI and AMP profiles need their own cases.

# Behavioral acceptance update

The user's clarified acceptance is equal successful results or failure on both sides,
without requiring equal exception classes/messages. This revision preserves the older
strict reports in the parent directory as historical evidence.

Native Designer 2025.1.2.165 GUI runs were actually observed. Native YXDB files are
unchanged; Python was recaptured against the current runtime. manual-review.json binds
the observed native outcomes to workflow/output hashes. See summary.json and the
per-run copies of native/Python captures, messages, probes and comparison reports.

| Workflow | Native/Python outcome | Matching data checkpoints | Behavioral verdict |
| --- | --- | --- | --- |
| Branch, duplicates, Unicode | success/success | 7 | match |
| Many-to-many Join | success/success | 7 | match |
| Empty branch | success/success | 7 | match |
| Null versus Formula empty string | success/success | 3 | match |
| Missing field | failed/failed, node 2 | 1 successful upstream output | match |
| Count Records and Select Records | success/success | 5 | match |

Total: **6 workflows, 30/30 data checkpoints**. Exception wording remains recorded;
the earlier KeyError versus native parse error is no longer an acceptance failure.
Strict metadata/diagnostic completeness remains unproven. These cases do not certify
all tools, configurations, model formats, output charts or external side effects.

The ready manual review bundle is reports/parity/manual-count-select. Its user
confirmations remain pending; they were not filled from the automated comparisons.

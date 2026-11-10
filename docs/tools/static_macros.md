# Local macro execution profiles

Python can execute an ordinary user-authored `.yxmc` graph using the canonical
parser and runtime. Macro Input/Output names route external frames to internal
nodes. Macro files resolve relative to the source workflow, then the installed
macro directory. The graph and each configured transformation execute normally;
this is not a passthrough replacement.

The 2026-11-10 continuation adds native question/Action binding, caller Value
answers, one-ControlParam batch reconfiguration and bounded iterative feedback.
Standard, batch and iterative examples are under examples/cli. Tests validate
actual transformed values, batch order, loop termination and zero-row batch
schemas when explicitly declared. Unsupported empty/dynamic schemas remain blocked.

Generated Python embeds local macro XML recursively and uses those snapshots even
after source files are deleted. Runtime macro dependencies used by native proof
are hashed; changed macro files invalidate prepared evidence. External data/model
dependencies remain real. Recursive macro file inclusion remains unsupported;
the explicit native IterativeMacro feedback profile is a separate mechanism.

These are configuration-specific local profiles, not proof of every native macro
mode, field map, iteration constant or output schema behavior. Native inner-macro
checkpoints are not automatically exported by outer graph probes. See
[Workflow CLI](../workflow_cli.md) for commands, supported Action modes and limits.

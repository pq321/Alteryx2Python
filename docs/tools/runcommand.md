# RunCommand

- Input anchor: `Input`
- Output anchor: `Output`

Workflow execution uses an explicit executable allowlist. The workflow CLI
and both generated scripts accept `--allow-command`. Phase One API callers
can set `allowed_commands` in the runtime configuration and can explicitly
request a dry run with `execute_commands: false`.

App Actions can bind an entire program, argument string, or working directory
to a text answer in a parameterized Phase Two export. Bound executables still
require allowlist approval at execution time.

When `CancelOnError` is explicitly false, an unsuccessful command or a missing
command result blocks its dependent nodes. Independent nodes can finish before
the workflow reports the error and runs the failure events. With cancellation
enabled, the command failure stops workflow execution immediately. A command
rejected by the allowlist fails immediately in either mode.

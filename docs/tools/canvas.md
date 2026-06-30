# Canvas and Sink Tools

Status: `L2_BASIC_IMPLEMENTATION`

Implemented semantics in the current slice:

- `TextBox`, `HtmlBox`, `ToolContainer`, and `ControlContainer` execute as structural no-op nodes
- `BrowseV2` and `Message` execute as terminal sink nodes
- inputs are recorded in the runtime trace when present
- no output anchors are emitted

Deferred semantics:

- Designer UI rendering
- Browse temp-file materialization
- Message warning/error policy and expression evaluation
- Tool container and control container enable/disable control-flow effects
- interface/action integration

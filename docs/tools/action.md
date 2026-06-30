# Action Tool

## Coverage

- Represents analytic-app Action nodes as executable metadata edges.
- Consumes `Question` or `Condition` payloads and emits an `Action` DataFrame.
- Records whether the action is active, the source branch/question value, and optional annotation metadata.
- Allows generated sample workflows to execute through `Action` edges without treating those edges as data rows.

## Deferred

- Mutating downstream tool configuration is not implemented.
- Action target modes such as replace/update formula/query/file path are preserved only as graph structure and metadata.
- Interactive analytic-app prompting remains outside the deterministic sample conversion baseline.

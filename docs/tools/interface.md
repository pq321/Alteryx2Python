# Interface Controls

## Coverage

- Parses analytic-app interface annotations for prompt/name metadata.
- Value controls emit a one-row `Question` output with `tool_type`, `name`, `prompt`, and `value`.
- Supported value controls: `DropDown`, `ListBox`, `NumericUpDown`, `QuestionFileBrowse`, `QuestionTextBox`, and `RadioButtonGroup`.
- Layout controls execute as structural no-op nodes: `Label`, `LabelGroup`, and `QuestionTab`.
- These baselines preserve interface nodes in generated Python scripts without simulating interactive app input.

## Deferred

- User interaction, app runtime prompting, and interface designer layout rendering.
- Action tool update semantics and Condition-controlled branch routing.
- Tool-specific option lists when they are stored outside the node configuration.

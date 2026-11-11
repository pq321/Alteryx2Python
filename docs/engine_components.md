# Engine Component Coverage (beyond tools)

Every engine component class maps to Python. Status after the
engine-components pass (tests: tests/test_engine_components/):

| Component | Python mapping | Status |
| --- | --- | --- |
| Workflow Events (RunBefore / RunAfter / failure / warnings phases) | workflow_events.py parses the native schema (cmd_Program / cmd_CommandArguments / When); executor runs commands via subprocess around the graph; mail events fail explicitly | implemented |
| Official built-in macros | local_macros.py: 14 native pandas implementations (CountRecords, SelectRecords, WeightedAvg, Imputation, RandomRecords, CreateSamples, MultiFieldBinning, Oversample, FieldSummary, Base64Encoder, JSONBuild, Spearman, Frequency, Contingency) | implemented |
| Generic + nested macros | macro_engine.py loads any .yxmc, binds MacroInput/MacroOutput anchors, applies interface answers, and executes the inner graph; nesting recurses through the same registry route (test: caller -> outer.yxmc -> CountRecords.yxmc) | implemented |
| Run Command tool | tools/runcommand.py with allow-listed subprocess execution | implemented |
| Python Tool (Jupyter) | tools/jupytercode.py executes the production notebook script with the ayx bridge: Alteryx.read('#1') / Alteryx.write(df, '#1'), notebook JSON code-cell extraction, stdout capture | implemented |
| Action tool (analytic app updates) | app_config.apply_actions: UpdateValue, UpdateValueReplace, UpdateValueFormula, UpdateRawXml, UpdateInput, UpdateOutput, UpdateSelect, UpdateFieldList, EditExpression, UpdateMap, DeleteTool; DynamicAction (data-driven) fails explicitly | implemented |
| Global / engine variables | engine_variables.py: the ten engine constants harvested from the native DLL string tables (WorkflowDirectory, WorkflowFileName, TempFilePath, ModuleDirectory, IterationNumber, OS, Version, Type, ReportFont, GuiInteraction) as [Engine.X] expression constants | implemented |
| User variables / question substitution | '%Question.<Name>%' percent tokens in any tool configuration string are resolved from bound answers before execution (executor pipeline + macro bodies); '%temp%' and '%Engine.X%' tokens resolve through the same layer | implemented |

Known explicit non-goals: SMTP event delivery without configured server
(recorded no-op), DynamicAction (requires per-record evaluation), and
Map/Tree question value adapters (fail with a typed error).

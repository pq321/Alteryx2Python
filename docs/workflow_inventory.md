# Workflow Inventory

## MIFID II

- Source file: `examples/sample_workflows/MIFID II.yxwz`
- Format: plain XML Alteryx workflow document despite the `.yxwz` extension
- Size: ~244 KB
- Node count: 43
- Connection count: 40

## Plugin Distribution

- `AlteryxBasePluginsGui.Formula.Formula`: 6
- `AlteryxBasePluginsGui.CrossTab.CrossTab`: 4
- `AlteryxBasePluginsGui.DbFileInput.DbFileInput`: 4
- `AlteryxBasePluginsGui.DynamicRename.DynamicRename`: 4
- `AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect`: 3
- `AlteryxBasePluginsGui.Transpose.Transpose`: 2
- `AlteryxBasePluginsGui.RecordID.RecordID`: 2
- `AlteryxBasePluginsGui.Union.Union`: 2
- `AlteryxBasePluginsGui.Join.Join`: 2
- `AlteryxGuiToolkit.ToolContainer.ToolContainer`: 2
- `AlteryxBasePluginsGui.JSONParse.JSONParse`: 2
- `AlteryxGuiToolkit.Action.Action`: 2
- `AlteryxBasePluginsGui.Filter.Filter`: 2
- `AlteryxBasePluginsGui.DbFileOutput.DbFileOutput`: 1
- `AlteryxGuiToolkit.Questions.TextBox.QuestionTextBox`: 1
- `AlteryxConnectorGui.Download.Download`: 1
- `AlteryxGuiToolkit.Questions.Tab.Tab`: 1
- `AlteryxGuiToolkit.Questions.FileBrowse.FileBrowse`: 1

## External Dependency Surface

The workflow references local workstation files that are not committed in this repository:

- `C:\Users\t796770\OneDrive - UBS\Alteryx\102928\EUC-43183-ROB-102928-RPP+Manual+Upload+Templates+Preparation-PROD26.04.27\DownloadData.xlsx|||output$`
- `C:\Users\t796770\OneDrive - UBS\Alteryx\102928\EUC-43183-ROB-102928-RPP+Manual+Upload+Templates+Preparation-PROD26.04.27\mapping.csv`
- `C:\Users\t796770\OneDrive - UBS\Alteryx\102928\EUC-43183-ROB-102928-RPP+Manual+Upload+Templates+Preparation-PROD26.04.27\MIFID output.xlsx|||Sheet1`
- `C:\Users\t796770\OneDrive - UBS\Alteryx\102928\EUC-43183-ROB-102928-RPP+Manual+Upload+Templates+Preparation-PROD26.04.27\ROB-102928 Input template - EQ.xlsx|||Sheet1$`

## Expected Unsupported Or Deferred Node Categories

These categories appear in the sample workflow and should not be treated as immediately executable in the canonical runtime:

- interface/question nodes
- action nodes
- tool containers
- download connector nodes
- output nodes that depend on unavailable external files

## Why This Workflow Matters

`MIFID II` is the first grounded end-to-end target for the project. It contains enough real structure to force decisions around parser fidelity, tool classification, expression support, graph execution, and unsupported-feature reporting.

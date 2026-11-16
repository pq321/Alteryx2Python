"""The Phase One palette scope selected from the nine Designer screenshots."""

from pathlib import Path
from xml.etree.ElementTree import ParseError

from alteryx2python.parser.xml_parser import TOOL_PARSERS, XmlWorkflowParser
from alteryx2python.tools.registry import TOOL_REGISTRY

PALETTE_SCOPE = {
    "In/Out": "BrowseV2 DateTimeNow Directory DbFileInput DbFileOutput TextInput",
    "Preparation": (
        "AutoField CreateSamples DataCleansePro DataCleansing Filter Formula GenerateRows "
        "Imputation MultiFieldBinning MultiFieldFormula MultiRowFormula OversampleField "
        "RandomRecords Rank RecordID Sample Select SelectRecords Sort Tile Unique"
    ),
    "Join": "AppendFields FindReplace FuzzyMatch Join JoinMultiple MakeGroup Union",
    "Parse": "DateTime RegEx TextToColumns XMLParse",
    "Transform": "Arrange CountRecords CrossTab MakeColumns RunningTotal Summarize Transpose WeightedAvg",
    "Reporting": (
        "Email PortfolioComposerImage PlotlyCharting PortfolioComposerLayout ReportLegendBuilder "
        "ReportLegendSplitter Overlay PortfolioComposerRender ReportFooter ReportHeader "
        "ReportMap PortfolioComposerText PortfolioComposerTable"
    ),
    "Documentation": "TextBox ToolContainer",
    "Interface": (
        "Action CheckBoxGroup Condition ControlParam Date DropDown Error QuestionFileBrowse "
        "FolderBrowse ListBox MacroInput MacroOutput NumericUpDown RadioButtonGroup QuestionTextBox"
    ),
    "Developer": (
        "Base64Encoder BlobConvert BlobInput BlobOutput BlockUntilDone ControlContainer Detour DetourEnd "
        "Download DynamicInput DynamicRename DynamicReplace DynamicSelect ExpectEqual FieldInfo JSONParse "
        "Message JupyterCode RunCommand"
    ),
}

WORKFLOW_FEATURES = (
    "disabled_container", "standard_macro", "nested_macro", "batch_macro", "iterative_macro",
    "app_questions_and_actions", "workflow_events", "user_variables", "global_variables",
)


def phase_one_scope(samples_root: Path | None = None) -> dict:
    registered = set(TOOL_REGISTRY.list_tool_types())
    rows = []
    for group, tool_types in PALETTE_SCOPE.items():
        for kind in tool_types.split():
            metadata = TOOL_REGISTRY.get(kind) if kind in registered else None
            rows.append({
                "category": group,
                "tool_type": kind,
                "config_parser": kind in TOOL_PARSERS,
                "runtime_profile": metadata.execution_profile if metadata else "unregistered",
            })
    sample_failures = []
    if samples_root is not None:
        if not samples_root.is_dir():
            raise ValueError(f"Sample directory is unavailable: {samples_root}")
        lookup = {row["tool_type"]: row for row in rows}
        for row in rows:
            row["configured_examples"] = []
        parser = XmlWorkflowParser()
        for path in sorted(samples_root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".yxmd", ".yxmc", ".yxwz"}:
                continue
            label = path.relative_to(samples_root).as_posix()
            try:
                kinds = {node.tool_type for node in parser.parse(path).nodes}
            except (ValueError, OSError, ParseError) as exc:
                sample_failures.append({"path": label, "error": str(exc)})
                continue
            for kind in kinds & lookup.keys():
                lookup[kind]["configured_examples"].append(label)
    return {
        "tool_count": len(rows),
        "tools": rows,
        "workflow_features": list(WORKFLOW_FEATURES),
        "sample_parse_failures": sample_failures,
        "scope_exclusions": [
            "Map Input", "Explorer Box", "DCM Connection", "Map question", "Tree",
            "Apache Spark Code", "API Output", "Test", "Throttle",
        ],
    }

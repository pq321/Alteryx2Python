from alteryx2python.tools.registry import TOOL_REGISTRY


def test_registry_contains_select_metadata():
    metadata = TOOL_REGISTRY.get("Select")
    assert metadata.tool_type == "Select"
    assert metadata.input_anchors == ("Input",)
    assert metadata.output_anchors == ("Output",)
    assert metadata.maturity == "L2_BASIC_IMPLEMENTATION"


def test_registry_contains_first_migrated_tool_set():
    assert TOOL_REGISTRY.list_tool_types() == [
        "APIOutput",
        "Action",
        "AlteryxReportChartGui",
        "AppendFields",
        "Arrange",
        "AutoField",
        "AutoML",
        "Barcode",
        "BasicDataProfile",
        "BlobConvert",
        "BlobInput",
        "BlobOutput",
        "BlockUntilDone",
        "BrowseV2",
        "Buffer",
        "BuildFeatures",
        "CalgaryCrossCount",
        "CalgaryCrossCountAppend",
        "CalgaryInput",
        "CalgaryJoin",
        "CalgaryLoader",
        "CheckBoxGroup",
        "Classification",
        "Condition",
        "ControlContainer",
        "CreatePoints",
        "CrossTab",
        "DataCleansePro",
        "DataCleansing",
        "Date",
        "DateTime",
        "DateTimeNow",
        "DbFileInput",
        "DbFileOutput",
        "Detour",
        "DetourEnd",
        "Directory",
        "Distance",
        "Download",
        "DropDown",
        "DynamicInput",
        "DynamicRename",
        "DynamicReplace",
        "DynamicSelect",
        "Error",
        "ExpectEqual",
        "FeatureTypes",
        "FieldInfo",
        "Filter",
        "FindNearest",
        "FindReplace",
        "Fit",
        "FolderBrowse",
        "Formula",
        "FuzzyMatch",
        "Generalize",
        "GenerateRows",
        "HtmlBox",
        "ImageProcessing",
        "ImageProfile",
        "ImageRecognition",
        "ImageTemplate",
        "ImageToText",
        "Insights",
        "JSONParse",
        "Join",
        "JoinMultiple",
        "JupyterCode",
        "KeyValuePairExtraction",
        "Label",
        "LabelGroup",
        "Link",
        "ListBox",
        "MakeColumns",
        "MakeGrid",
        "MakeGroup",
        "Map",
        "MapInput",
        "Message",
        "Modeling",
        "MultiFieldFormula",
        "MultiRowFormula",
        "NamedEntityRecognition",
        "NumericUpDown",
        "Overlay",
        "PDFInput",
        "PDFToText",
        "PartOfSpeechTagger",
        "PearsonCorrelation",
        "PlotlyCharting",
        "PolyBuild",
        "PolySplit",
        "PortfolioComposerImage",
        "PortfolioComposerLayout",
        "PortfolioComposerRender",
        "PortfolioComposerTable",
        "PortfolioComposerText",
        "Predict",
        "QuestionFileBrowse",
        "QuestionTab",
        "QuestionTextBox",
        "RadioButtonGroup",
        "Rank",
        "RecordID",
        "RegEx",
        "Regression",
        "ReportFooter",
        "ReportHeader",
        "ReportLegendBuilder",
        "ReportLegendSplitter",
        "ReportMap",
        "RunCommand",
        "RunningTotal",
        "Sample",
        "Select",
        "Sentiment",
        "Smooth",
        "Sort",
        "SpatialInfo",
        "SpatialMatch",
        "SpatialProcess",
        "Summarize",
        "Test",
        "TextBox",
        "TextInput",
        "TextPreProcessing",
        "TextSummary",
        "TextToColumns",
        "Throttle",
        "Tile",
        "ToolContainer",
        "TopicModel",
        "TradeArea",
        "Transformation",
        "Transpose",
        "Tree",
        "UNKNOWN",
        "Union",
        "Unique",
        "VisualLayout",
        "WordCloud",
        "XMLParse",
        "ZeroShotTextClassification",
    ]

    assert TOOL_REGISTRY.get("APIOutput").output_anchors == ()
    assert TOOL_REGISTRY.get("Action").output_anchors == ("Action",)
    assert TOOL_REGISTRY.get("AlteryxReportChartGui").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("CrossTab").semantics_doc == "docs/tools/crosstab.md"
    assert TOOL_REGISTRY.get("AppendFields").input_anchors == ("Targets", "Source")
    assert TOOL_REGISTRY.get("Arrange").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("AutoField").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("BasicDataProfile").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("BlobConvert").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("BlobInput").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("BlobOutput").output_anchors == ()
    assert TOOL_REGISTRY.get("BlockUntilDone").output_anchors == ("Output", "Output2", "Output3")
    assert TOOL_REGISTRY.get("Buffer").semantics_doc == "docs/tools/buffer.md"
    assert TOOL_REGISTRY.get("BrowseV2").output_anchors == ()
    assert TOOL_REGISTRY.get("CheckBoxGroup").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("Condition").output_anchors == ("True Condition", "False Condition")
    assert TOOL_REGISTRY.get("ControlContainer").output_anchors == ()
    assert TOOL_REGISTRY.get("CreatePoints").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("DataCleansePro").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("DataCleansing").input_anchors == ("Input2",)
    assert TOOL_REGISTRY.get("DataCleansing").output_anchors == ("Output26",)
    assert TOOL_REGISTRY.get("Date").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("DateTime").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("DateTimeNow").input_anchors == ()
    assert TOOL_REGISTRY.get("DbFileInput").input_anchors == ()
    assert TOOL_REGISTRY.get("DbFileInput").supports_certification is True
    assert TOOL_REGISTRY.get("DbFileOutput").output_anchors == ()
    assert TOOL_REGISTRY.get("DbFileOutput").supports_certification is True
    assert TOOL_REGISTRY.get("Detour").output_anchors == ("Left", "Right")
    assert TOOL_REGISTRY.get("DetourEnd").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Distance").semantics_doc == "docs/tools/distance.md"
    assert TOOL_REGISTRY.get("Distance").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Directory").input_anchors == ()
    assert TOOL_REGISTRY.get("Download").input_anchors == ("Input",)
    assert TOOL_REGISTRY.get("Download").supports_certification is False
    assert TOOL_REGISTRY.get("DropDown").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("DynamicInput").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("DynamicRename").input_anchors == ("Targets",)
    assert TOOL_REGISTRY.get("DynamicReplace").output_anchors == ("Output", "Counts")
    assert TOOL_REGISTRY.get("DynamicSelect").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Error").output_anchors == ()
    assert TOOL_REGISTRY.get("ExpectEqual").output_anchors == ()
    assert TOOL_REGISTRY.get("FieldInfo").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("FindNearest").output_anchors == ("Matched",)
    assert TOOL_REGISTRY.get("FindReplace").input_anchors == ("Targets", "Source")
    assert TOOL_REGISTRY.get("FolderBrowse").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("Formula").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("FuzzyMatch").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("GenerateRows").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Generalize").semantics_doc == "docs/tools/generalize.md"
    assert TOOL_REGISTRY.get("HtmlBox").output_anchors == ()
    assert TOOL_REGISTRY.get("Filter").output_anchors == ("True", "False")
    assert TOOL_REGISTRY.get("Join").output_anchors == ("Join", "Left", "Right")
    assert TOOL_REGISTRY.get("Join").supports_certification is True
    assert TOOL_REGISTRY.get("JoinMultiple").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("JSONParse").input_anchors == ("Input",)
    assert TOOL_REGISTRY.get("JupyterCode").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Label").output_anchors == ()
    assert TOOL_REGISTRY.get("LabelGroup").output_anchors == ()
    assert TOOL_REGISTRY.get("Link").output_anchors == ()
    assert TOOL_REGISTRY.get("ListBox").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("MakeColumns").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("MakeGrid").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("MakeGroup").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Map").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("MapInput").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Message").output_anchors == ()
    assert TOOL_REGISTRY.get("MultiFieldFormula").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("MultiRowFormula").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("NumericUpDown").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("Overlay").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("PDFInput").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("PDFToText").input_anchors == ("Data Input", "Template Input")
    assert TOOL_REGISTRY.get("PearsonCorrelation").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("PolyBuild").semantics_doc == "docs/tools/polybuild.md"
    assert TOOL_REGISTRY.get("PolySplit").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("PlotlyCharting").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("PortfolioComposerImage").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("PortfolioComposerLayout").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("PortfolioComposerRender").output_anchors == ()
    assert TOOL_REGISTRY.get("PortfolioComposerTable").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("PortfolioComposerText").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("QuestionFileBrowse").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("QuestionTab").output_anchors == ()
    assert TOOL_REGISTRY.get("QuestionTextBox").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("RadioButtonGroup").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("RecordID").semantics_doc == "docs/tools/recordid.md"
    assert TOOL_REGISTRY.get("Rank").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("RegEx").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("ReportFooter").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("ReportHeader").output_anchors == ("Output13",)
    assert TOOL_REGISTRY.get("ReportLegendBuilder").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("ReportLegendSplitter").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("ReportMap").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("RunCommand").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("RunningTotal").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Sample").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Smooth").semantics_doc == "docs/tools/smooth.md"
    assert TOOL_REGISTRY.get("Sort").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Summarize").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Test").output_anchors == ()
    assert TOOL_REGISTRY.get("TextBox").output_anchors == ()
    assert TOOL_REGISTRY.get("Select").supports_certification is True
    assert TOOL_REGISTRY.get("SpatialInfo").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("SpatialMatch").output_anchors == ("Matched",)
    assert TOOL_REGISTRY.get("SpatialProcess").semantics_doc == "docs/tools/spatialprocess.md"
    assert TOOL_REGISTRY.get("TextInput").supports_certification is True
    assert TOOL_REGISTRY.get("TextToColumns").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Throttle").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Tile").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("ToolContainer").output_anchors == ()
    assert TOOL_REGISTRY.get("TradeArea").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Transpose").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Tree").output_anchors == ("Question",)
    assert TOOL_REGISTRY.get("Union").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Unique").output_anchors == ("Unique", "Duplicate")
    assert TOOL_REGISTRY.get("VisualLayout").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("XMLParse").output_anchors == ("Output",)
    for tool_type in [
        "AutoML",
        "Barcode",
        "BuildFeatures",
        "CalgaryCrossCount",
        "CalgaryCrossCountAppend",
        "CalgaryInput",
        "CalgaryJoin",
        "CalgaryLoader",
        "Classification",
        "FeatureTypes",
        "Fit",
        "ImageProcessing",
        "ImageProfile",
        "ImageRecognition",
        "ImageTemplate",
        "ImageToText",
        "Insights",
        "KeyValuePairExtraction",
        "Modeling",
        "NamedEntityRecognition",
        "PartOfSpeechTagger",
        "Predict",
        "Regression",
        "Sentiment",
        "TextPreProcessing",
        "TextSummary",
        "TopicModel",
        "Transformation",
        "UNKNOWN",
        "WordCloud",
        "ZeroShotTextClassification",
    ]:
        assert TOOL_REGISTRY.get(tool_type).semantics_doc == "docs/tools/baseline.md"

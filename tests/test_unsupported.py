from alteryx2python.unsupported import classify_tool


def test_classify_supported_tool_as_safe_to_attempt():
    decision = classify_tool("Select")

    assert decision.classification == "safe_to_attempt"
    assert decision.reason == "Tool has baseline runtime semantics"


def test_classify_action_tool_as_safe_to_attempt():
    decision = classify_tool("Action")

    assert decision.classification == "safe_to_attempt"
    assert decision.reason == "Tool has baseline runtime semantics"


def test_classify_interface_baseline_tools_as_safe_to_attempt():
    for tool_type in ["CheckBoxGroup", "ControlParam", "Date", "FolderBrowse", "Link", "Map", "Tree"]:
        decision = classify_tool(tool_type)

        assert decision.classification == "safe_to_attempt"


def test_classify_developer_and_spatial_baseline_tools_as_safe_to_attempt():
    for tool_type in ["BlobOutput", "Detour", "DetourEnd", "PolySplit", "RunCommand", "Throttle"]:
        decision = classify_tool(tool_type)

        assert decision.classification == "safe_to_attempt"


def test_classify_transform_investigation_and_reporting_tools_as_safe_to_attempt():
    for tool_type in [
        "AlteryxReportChartGui",
        "APIOutput",
        "Arrange",
        "AutoML",
        "Barcode",
        "BasicDataProfile",
        "BlobInput",
        "BuildFeatures",
        "CalgaryCrossCount",
        "CalgaryCrossCountAppend",
        "CalgaryInput",
        "CalgaryJoin",
        "CalgaryLoader",
        "Classification",
        "DynamicInput",
        "DynamicReplace",
        "ExpectEqual",
        "FeatureTypes",
        "Fit",
        "FuzzyMatch",
        "ImageProcessing",
        "ImageProfile",
        "ImageRecognition",
        "ImageTemplate",
        "ImageToText",
        "Insights",
        "JupyterCode",
        "KeyValuePairExtraction",
        "MacroInput",
        "MakeGrid",
        "MakeGroup",
        "Modeling",
        "NamedEntityRecognition",
        "Overlay",
        "PartOfSpeechTagger",
        "PDFInput",
        "PDFToText",
        "Predict",
        "Regression",
        "Sentiment",
        "TextPreProcessing",
        "TextSummary",
        "TopicModel",
        "Transformation",
        "UNKNOWN",
        "VisualLayout",
        "WordCloud",
        "ZeroShotTextClassification",
    ]:
        decision = classify_tool(tool_type)

        assert decision.classification == "safe_to_attempt"


def test_classify_unknown_tool_as_custom_code_required():
    decision = classify_tool("UnknownTool")

    assert decision.classification == "custom_code_required"

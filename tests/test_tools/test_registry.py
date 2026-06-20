from alteryx2python.tools.registry import TOOL_REGISTRY


def test_registry_contains_select_metadata():
    metadata = TOOL_REGISTRY.get("Select")
    assert metadata.tool_type == "Select"
    assert metadata.input_anchors == ("Input",)
    assert metadata.output_anchors == ("Output",)
    assert metadata.maturity == "L2_BASIC_IMPLEMENTATION"


def test_registry_contains_first_migrated_tool_set():
    assert TOOL_REGISTRY.list_tool_types() == [
        "CrossTab",
        "DbFileInput",
        "DbFileOutput",
        "DynamicRename",
        "Filter",
        "Formula",
        "JSONParse",
        "Join",
        "RecordID",
        "Select",
        "Sort",
        "TextInput",
        "Transpose",
        "Union",
    ]

    assert TOOL_REGISTRY.get("CrossTab").semantics_doc == "docs/tools/crosstab.md"
    assert TOOL_REGISTRY.get("DbFileInput").input_anchors == ()
    assert TOOL_REGISTRY.get("DbFileInput").supports_certification is True
    assert TOOL_REGISTRY.get("DbFileOutput").output_anchors == ()
    assert TOOL_REGISTRY.get("DbFileOutput").supports_certification is True
    assert TOOL_REGISTRY.get("DynamicRename").input_anchors == ("Targets",)
    assert TOOL_REGISTRY.get("Formula").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Filter").output_anchors == ("True", "False")
    assert TOOL_REGISTRY.get("Join").output_anchors == ("Join", "Left", "Right")
    assert TOOL_REGISTRY.get("Join").supports_certification is True
    assert TOOL_REGISTRY.get("JSONParse").input_anchors == ("Input",)
    assert TOOL_REGISTRY.get("RecordID").semantics_doc == "docs/tools/recordid.md"
    assert TOOL_REGISTRY.get("Sort").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Select").supports_certification is True
    assert TOOL_REGISTRY.get("TextInput").supports_certification is True
    assert TOOL_REGISTRY.get("Transpose").output_anchors == ("Output",)
    assert TOOL_REGISTRY.get("Union").output_anchors == ("Output",)

from alteryx2python.tools.registry import TOOL_REGISTRY


def test_registry_contains_select_metadata():
    metadata = TOOL_REGISTRY.get("Select")
    assert metadata.tool_type == "Select"
    assert metadata.input_anchors == ("Input",)
    assert metadata.output_anchors == ("Output",)
    assert metadata.maturity == "L2_BASIC_IMPLEMENTATION"
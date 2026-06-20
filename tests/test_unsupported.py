from alteryx2python.unsupported import classify_tool


def test_classify_supported_tool_as_safe_to_attempt():
    decision = classify_tool("Select")

    assert decision.classification == "safe_to_attempt"
    assert decision.reason == "Tool has baseline runtime semantics"


def test_classify_interface_tool_as_owner_review_required():
    decision = classify_tool("Action")

    assert decision.classification == "owner_review_required"


def test_classify_unknown_tool_as_custom_code_required():
    decision = classify_tool("UnknownTool")

    assert decision.classification == "custom_code_required"

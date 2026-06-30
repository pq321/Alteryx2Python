from alteryx2python.tools.datetimenow import datetimenow_tool


def test_datetimenow_uses_injected_clock(workflow_context):
    output = datetimenow_tool(
        {},
        {"output_format": "yyyy-MM-dd", "now": "2026-06-22T15:04:05"},
        workflow_context,
    )["Output"]

    assert output.to_dict("records") == [{"DateTimeNow": "2026-06-22"}]

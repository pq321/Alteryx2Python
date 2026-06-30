from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR
from alteryx2python.support_surfaces import build_support_map


def _node(node_id, tool_type, config):
    return NodeIR(
        node_id=node_id,
        source_tool_id=node_id,
        tool_type=tool_type,
        tool_name=tool_type,
        config={"normalized": config},
        input_anchors=[AnchorIR("Input", "input")],
        output_anchors=[AnchorIR("Output", "output")],
        supported_status="L2_BASIC_IMPLEMENTATION",
    )


def test_support_map_extracts_report_change_surfaces():
    workflow = WorkflowIR(
        workflow_id="wf",
        workflow_name="report workflow",
        source_file="report.yxmd",
        source_hash="hash",
        parser_version="0.1.0",
        migration_spec_version="0.1.0",
        nodes=[
            _node("1", "DbFileInput", {"file": "input.csv"}),
            _node("2", "PortfolioComposerText", {"message": "Hello", "rich_text": "<p>Hello</p>"}),
            _node("3", "PortfolioComposerTable", {"table_fields": ["account", "amount"]}),
            _node("4", "PortfolioComposerRender", {"output_file": "report.html", "data_field": "Report"}),
        ],
        edges=[
            EdgeIR("1:Output->2:Input", "1", "Output", "2", "Input"),
            EdgeIR("2:Output->4:Input", "2", "Output", "4", "Input"),
        ],
    )

    support_map = build_support_map(workflow)

    assert support_map["change_request_index"]["inputs"] == ["1"]
    assert support_map["change_request_index"]["body_candidates"] == ["2"]
    assert support_map["change_request_index"]["table_candidates"] == ["3"]
    assert support_map["change_request_index"]["attachment_candidates"] == ["4"]
    body_surface = support_map["surfaces"][1]
    assert body_surface["editable_fields"] == ["message", "rich_text"]
    assert body_surface["graph_context"]["incoming"][0]["source_tool_type"] == "DbFileInput"

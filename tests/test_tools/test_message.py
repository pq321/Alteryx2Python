import pandas as pd
import pytest

from alteryx2python.parity.samples import generate_control_log_sample
from alteryx2python.tools.canvas import message_tool
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.executor import run_workflow_graph
from alteryx2python.workflow_generator import WorkflowBuilder


def test_message_filters_records_emits_warnings_and_preserves_data(workflow_context):
    source = pd.DataFrame({"label": ["keep", "alert", "later"], "count": [0, 3, 5]})
    config = {
        "when": "Filter", "filter": "[count] > 2", "type": "Warning",
        "message_expression": "[label]",
    }
    output = message_tool({"Input": source}, config, workflow_context)["Output"]
    pd.testing.assert_frame_equal(output, source)
    assert workflow_context.warnings == ["alert", "later"]
    assert [item["severity"] for item in workflow_context.diagnostics] == ["warning", "warning"]


def test_message_error_fails_on_the_triggered_record(workflow_context):
    config = {"when": "Last", "type": "Error", "message_expression": "[label]"}
    with pytest.raises(ValueError, match="second"):
        message_tool({"Input": pd.DataFrame({"label": ["first", "second"]})}, config, workflow_context)


def test_message_after_all_waits_for_downstream_nodes(workflow_context, tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["x"], [["1"]])
    after = builder._node(
        "Message", '<When>All</When><Type>Message</Type><MessageExpression>"after"</MessageExpression>', (150, 100)
    )
    downstream = builder._node(
        "Message", '<When>First</When><Type>Message</Type><MessageExpression>"before"</MessageExpression>', (250, 100)
    )
    builder.connect(source, after)
    builder.connect(after, downstream)
    path = tmp_path / "messages.yxmd"
    path.write_text(builder.render(), encoding="utf-8")
    run_workflow_graph(XmlWorkflowParser().parse(path), workflow_context)
    assert [entry["message"] for entry in workflow_context.diagnostics] == ["before", "after"]
    assert workflow_context.deferred_messages == []


def test_control_log_is_emitted_after_members_and_used_as_control_input(workflow_context, tmp_path):
    [path] = generate_control_log_sample(tmp_path / "source")
    workflow = XmlWorkflowParser().parse(path)

    result = run_workflow_graph(workflow, workflow_context)

    order = result.execution_order
    assert order.index("5") < order.index("2") < order.index("6") < order.index("3")
    log = result.node_results["2"].outputs["Log"]
    assert log.values.tolist() == [
        [2, "Info", "Control Container Activated."],
        [4, "Warning", "warning in first container"],
        [5, "Info", "last message in first container"],
        [2, "Info", "Control Container Completed."],
    ]
    assert result.node_results["3"].outputs["Log"]["Message"].tolist() == [
        "Control Container Activated.", "message in second container", "Control Container Completed.",
    ]
    assert workflow_context.warnings == ["warning in first container"]

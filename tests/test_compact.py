from alteryx2python.compact import build_compact_workflow
from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR


def _workflow() -> WorkflowIR:
    return WorkflowIR(
        workflow_id="wf",
        workflow_name="Compact Example",
        source_file="example.yxmd",
        source_hash="hash",
        parser_version="0.1.0",
        migration_spec_version="0.1.0",
        nodes=[
            NodeIR(
                node_id="1",
                source_tool_id="1",
                tool_type="DbFileInput",
                tool_name="AlteryxBasePluginsGui.DbFileInput.DbFileInput",
                config={
                    "raw": {"Position": {"x": "1", "y": "2"}},
                    "normalized": {
                        "file": "C:/data/customers.csv",
                        "file_attributes": {"FileFormat": "0"},
                        "base_dir": "C:/data",
                    },
                },
                output_anchors=[AnchorIR("Output", "output")],
                outgoing_edges=["1:Output->2:Input"],
                metadata={
                    "raw_gui_settings": {"Position": {"x": "1", "y": "2"}},
                    "annotation": {"text": "UI note"},
                    "meta_info": {},
                },
                supported_status="L2_BASIC_IMPLEMENTATION",
            ),
            NodeIR(
                node_id="2",
                source_tool_id="2",
                tool_type="Select",
                tool_name="AlteryxBasePluginsGui.AlteryxSelect.AlteryxSelect",
                config={
                    "raw": {"SelectFields": "large raw payload"},
                    "normalized": {
                        "select_fields": [
                            {"source": "account", "rename": "customer", "selected": True},
                            {"source": "amount", "rename": "amount", "selected": True},
                        ],
                        "base_dir": "C:/data",
                    },
                },
                input_anchors=[AnchorIR("Input", "input")],
                output_anchors=[AnchorIR("Output", "output")],
                incoming_edges=["1:Output->2:Input"],
                expected_output_schema={
                    "fields": [
                        {"name": "customer", "type": "V_String", "source": "verbose source path"},
                        {"name": "amount", "type": "Double"},
                    ]
                },
                metadata={"raw_gui_settings": {"Position": {"x": "3", "y": "4"}}},
                supported_status="L2_BASIC_IMPLEMENTATION",
            ),
        ],
        edges=[
            EdgeIR(
                edge_id="1:Output->2:Input",
                source_node_id="1",
                source_anchor="Output",
                target_node_id="2",
                target_anchor="Input",
                metadata={"raw": {"ignored": True}},
            )
        ],
        external_dependencies=["C:/data/customers.csv"],
    )


def test_compact_workflow_preserves_topology_without_raw_shell_data():
    compact = build_compact_workflow(_workflow())

    assert compact["workflow"]["node_count"] == 2
    assert compact["workflow"]["edge_count"] == 1
    assert compact["graph"]["roots"] == ["1"]
    assert compact["graph"]["leaves"] == ["2"]
    assert compact["graph"]["topological_order"] == ["1", "2"]
    assert compact["edges"] == [
        {
            "id": "1:Output->2:Input",
            "from_node": "1",
            "from_anchor": "Output",
            "to_node": "2",
            "to_anchor": "Input",
        }
    ]

    input_node, select_node = compact["nodes"]
    assert input_node["outputs"] == ["Output"]
    assert select_node["inputs"] == ["Input"]
    assert select_node["incoming"] == [{"from": "1:Output", "to": "2:Input"}]
    assert input_node["outgoing"] == [{"from": "1:Output", "to": "2:Input"}]
    assert input_node["config_summary"] == {
        "file": "C:/data/customers.csv",
        "file_name": "customers.csv",
        "file_attributes": {"FileFormat": "0"},
    }
    assert select_node["config_summary"]["select_fields"][0]["rename"] == "customer"
    assert select_node["schema_summary"]["Output"] == [
        {"name": "customer", "type": "V_String"},
        {"name": "amount", "type": "Double"},
    ]

    rendered = str(compact)
    assert "raw_gui_settings" not in rendered
    assert "large raw payload" not in rendered
    assert "verbose source path" not in rendered
    assert "Position" not in rendered

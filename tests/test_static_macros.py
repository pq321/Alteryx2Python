from pathlib import Path

import pandas as pd
import pytest

from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.runtime.executor import run_workflow_graph


def test_user_static_macro_executes_original_graph_and_routes_named_boundaries(tmp_path):
    macro = tmp_path / "Double.yxmc"
    macro.write_text('''<AlteryxDocument><Nodes>
      <Node ToolID="1"><GuiSettings Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput"/><Properties><Configuration><Name>Input</Name></Configuration></Properties></Node>
      <Node ToolID="2"><GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"/><Properties><Configuration><FormulaFields><FormulaField field="twice" expression="[x] * 2" type="Double"/></FormulaFields></Configuration></Properties></Node>
      <Node ToolID="3"><GuiSettings Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput"/><Properties><Configuration><Name>Output</Name></Configuration></Properties></Node>
    </Nodes><Connections>
      <Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>
      <Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>
    </Connections></AlteryxDocument>''', encoding="utf-8")
    source = tmp_path / "outer.yxmd"
    source.write_text('''<AlteryxDocument><Nodes><Node ToolID="10"><GuiSettings/><Properties><Configuration/></Properties><EngineSettings Macro="Double.yxmc"/></Node></Nodes></AlteryxDocument>''', encoding="utf-8")
    workflow = XmlWorkflowParser().parse(source)
    assert workflow.nodes[0].tool_type == "Macro_Double"
    result = run_workflow_graph(workflow, WorkflowContext(), initial_inputs={"10": {"Input": pd.DataFrame({"x": [1, 3]})}})
    assert result.node_results["10"].outputs["Output"].to_dict("records") == [{"x": 1, "twice": 2}, {"x": 3, "twice": 6}]


def test_missing_macro_is_an_implementation_blocker(tmp_path):
    source = tmp_path / "outer.yxmd"
    source.write_text('''<AlteryxDocument><Nodes><Node ToolID="1"><GuiSettings/><Properties><Configuration/></Properties><EngineSettings Macro="Missing.yxmc"/></Node></Nodes></AlteryxDocument>''')
    with pytest.raises(NotImplementedError, match="unavailable"):
        run_workflow_graph(XmlWorkflowParser().parse(source), WorkflowContext())

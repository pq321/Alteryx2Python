"""Web API contracts and canonical execution, without native parity claims."""
from __future__ import annotations

import base64
from email import policy
from email.parser import BytesParser
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import sys
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "webapp"))
import server
from backend import ApiError
from graph_compiler import compile_graph_to_yxmd
from tool_palette import build_palette, blocked_reason
from workflow_documents import import_macro, import_workflow, parse_element
from alteryx2python.parser.xml_parser import XmlWorkflowParser
from alteryx2python.tools.registry import TOOL_REGISTRY
from alteryx2python.workflow_generator import WorkflowBuilder


def simple_graph():
    return {"name": "editable", "nodes": [{"id": "42", "type": "TextInput", "config": {
        "fields": ["amount"], "rows": [["2"], ["5"]]}}], "edges": []}


def graph_from_xml(xml, tmp_path, name="source.yxwz"):
    return import_workflow({"name": name, "xml": xml, "sourcePath": str(tmp_path / name)}, tmp_path)


def shape(element):
    return (element.tag, element.attrib, (element.text or "").strip(), [shape(child) for child in element])


def test_palette_is_registry_derived_and_excludes_fake_adapters():
    palette = build_palette(server.SIMPLE_TOOLS)
    types = {tool["type"] for tool in palette["tools"]}
    implemented = {kind for kind in TOOL_REGISTRY.list_tool_types() if not blocked_reason(TOOL_REGISTRY.get(kind))}
    assert types == implemented | {"Macro"}
    assert {"Action", "JupyterCode", "Email", "RunCommand", "WaitSeconds", "MacroOutput"} <= types
    assert not {"APIOutput", "BlobOutput", "DynamicInput", "FuzzyMatch", "PDFInput", "UNKNOWN"} & types
    for tool in palette["tools"]:
        assert tool["advancedConfig"]
        assert isinstance(tool["inputs"], list) and isinstance(tool["outputs"], list)
    assert palette["workflowConfig"]["runtime"]["allowed_commands"] == []


@pytest.mark.parametrize("suffix", [".yxmd", ".yxwz", ".yxmc"])
def test_import_export_preserves_properties_nested_nodes_and_wire_metadata(tmp_path, suffix):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["label"], [["original"]])
    target = builder.add_select([("label", "True")])
    builder.connect(source, target)
    root = ET.fromstring(builder.render())
    root.set("customRootAttribute", "preserve")
    nodes = root.find("Nodes")
    child = nodes.find("Node")
    nodes.remove(child)
    container = ET.SubElement(nodes, "Node", ToolID="99")
    gui = ET.SubElement(container, "GuiSettings", Plugin="AlteryxGuiToolkit.ToolContainer.ToolContainer")
    ET.SubElement(gui, "Position", x="2", y="3")
    ET.SubElement(ET.SubElement(container, "Properties"), "Configuration")
    ET.SubElement(container, "ChildNodes").append(child)
    ET.SubElement(child.find("Properties"), "VendorOption", keep="yes").text = "original"
    properties = root.find("Properties")
    ET.SubElement(properties, "VendorProperties", keep="yes").text = "metadata"
    ET.SubElement(properties, "Events").append(ET.fromstring('<Event><Enabled value="False"/><When>AfterRun</When><cmd_Program>never.exe</cmd_Program></Event>'))
    runtime = properties.find("RuntimeProperties")
    if runtime is None:
        runtime = ET.SubElement(properties, "RuntimeProperties")
    ET.SubElement(runtime, "Actions", custom="preserve")
    ET.SubElement(runtime, "Questions")
    root.find("Connections/Connection").set("Wireless", "True")
    source_xml = ET.tostring(root, encoding="unicode")
    graph = graph_from_xml(source_xml, tmp_path, "source" + suffix)
    assert next(node for node in graph["nodes"] if node["id"] == str(source))["parentId"] == "99"
    assert shape(ET.fromstring(compile_graph_to_yxmd(graph))) == shape(root)
    graph["nodes"][0]["config"]["configurationXml"] = '<Configuration><Custom value="edited" /></Configuration>'
    edited = ET.fromstring(compile_graph_to_yxmd(graph))
    assert shape(edited.find("Properties")) == shape(properties)
    assert edited.find("Connections/Connection").get("Wireless") == "True"
    assert edited.find(".//VendorOption").text == "original"


def test_raw_node_and_workflow_edit_scopes_are_independent(tmp_path):
    graph = simple_graph()
    graph = graph_from_xml(compile_graph_to_yxmd(graph), tmp_path)
    graph["eventsXml"] = '<Events><Enabled value="False"/><Event custom="keep"/></Events>'
    graph["runtimePropertiesXml"] = '<RuntimeProperties><ModuleType>Standard</ModuleType><Questions/><Actions/></RuntimeProperties>'
    graph["constantsXml"] = '<Constants><Constant><Namespace>User</Namespace><Name>label</Name><Value>test</Value></Constant></Constants>'
    graph["nodes"][0]["config"]["engineSettingsXml"] = '<EngineSettings EngineDll="custom.dll" CustomOption="keep" />'
    xml = ET.fromstring(compile_graph_to_yxmd(graph))
    assert xml.find("Nodes/Node/EngineSettings").get("CustomOption") == "keep"
    assert xml.find("Properties/Constants/Constant/Value").text == "test"
    assert xml.find("Properties/RuntimeProperties/Actions") is not None
    assert xml.find("Properties/Events/Event").get("custom") == "keep"
    graph["eventsXml"] = "<RuntimeProperties />"
    with pytest.raises(ValueError, match="Events"):
        compile_graph_to_yxmd(graph)


def test_phase_two_export_executes_without_repository_imports_and_keeps_ids(tmp_path):
    graph = simple_graph()
    graph["nodes"].append({"id": "75", "type": "DbFileOutput", "config": {"file": "answer.csv"}})
    graph["edges"] = [{"from": "42", "to": "75"}]
    result = server._compile(graph)
    assert result["phase2Status"] == "compiled" and result["unsupported"] == []
    assert "alteryx2python" not in result["python"] and "alteryx_runtime" not in result["python"]
    namespace = {"__file__": str(tmp_path / "native.py")}
    exec(result["python"], namespace)
    namespace["run_workflow"](input_dir=tmp_path, output_dir=tmp_path / "output")
    assert pd.read_csv(tmp_path / "output/answer.csv")["amount"].tolist() == [2, 5]
    assert {node.get("ToolID") for node in ET.fromstring(result["yxmd"]).iter("Node")} == {"42", "75"}


def test_constants_overrides_reach_both_runtime_and_canonical_compiler(tmp_path):
    builder = WorkflowBuilder()
    source = builder.add_text_input(["amount"], [["2"]])
    formula = builder.add_formula([("result", "Double", "8", "[amount] * [User.rate]")])
    builder.connect(source, formula)
    graph = graph_from_xml(builder.render(), tmp_path)
    graph["constantsXml"] = '<Constants><Constant><Namespace>User</Namespace><Name>rate</Name><Value>3</Value><IsNumeric value="True" /></Constant></Constants>'
    graph["runtime"] = {"constants": {"User.rate": 4}}
    result = server._run(graph)
    assert result["rows"] == [[2, 8.0]]
    assert result["manifest"]["workflow_constants"]["User.rate"] == 4


def app_xml():
    builder = WorkflowBuilder()
    source = builder.add_text_input(["amount"], [["2"], ["5"]])
    target = builder.add_filter("[amount] > __LIMIT__")
    builder.connect(source, target)
    root = ET.fromstring(builder.render())
    properties = root.find("Properties")
    previous = properties.find("RuntimeProperties")
    if previous is not None:
        properties.remove(previous)
    runtime = ET.SubElement(properties, "RuntimeProperties")
    ET.SubElement(runtime, "ModuleType").text = "Wizard"
    question = ET.SubElement(ET.SubElement(runtime, "Questions"), "Question")
    for key, value in {"Type": "NumericUpDown", "Name": "limit", "ToolId": "90", "Default": "3"}.items():
        ET.SubElement(question, key).text = value
    action = ET.SubElement(ET.SubElement(ET.SubElement(ET.SubElement(runtime, "Actions"), "NoCondition"), "True"), "Action")
    for key, value in {"Type": "UpdateValueReplace", "Variable": "limit", "Destination": f"{target}/Expression", "ReplaceText": "__LIMIT__"}.items():
        ET.SubElement(action, key).text = value
    return ET.tostring(root, encoding="unicode")


@pytest.mark.parametrize("mode", ["dynamic", "specialized"])
def test_questions_actions_and_parameter_mode_reach_runtime_and_phase_two(tmp_path, mode):
    graph = graph_from_xml(app_xml(), tmp_path)
    graph["runtime"], graph["parameterMode"] = {"answers": {"limit": 4}}, mode
    result = server._run(graph)
    true_output = next(p for p in result["previews"] if p["node"] == "2" and p["anchor"] == "True")
    assert true_output["rows"] == [[5]]
    assert result["phase2Status"] == "compiled", result["blockers"]
    assert result["manifest"]["parameter_mode"] == mode
    assert "RuntimeProperties" in result["yxmd"]


def test_select_and_formula_keep_declared_metadata():
    graph = simple_graph()
    graph["nodes"].extend([
        {"id": "60", "type": "Select", "config": {"fields": [{"field": "amount", "selected": "True", "type": "FixedDecimal", "size": "10", "scale": "2", "rename": "total"}]}},
        {"id": "70", "type": "Formula", "config": {"expressions": [{"field": "tax", "type": "FixedDecimal", "size": "10", "scale": "3", "expression": "[total]"}]}},
    ])
    root = ET.fromstring(compile_graph_to_yxmd(graph))
    selected = root.find(".//SelectField")
    assert {key: selected.get(key) for key in ("type", "size", "scale", "rename")} == {"type": "FixedDecimal", "size": "10", "scale": "2", "rename": "total"}
    assert root.find(".//FormulaField").get("scale") == "3"


def macro_xml(nested=None):
    middle = ('<Node ToolID="2"><GuiSettings Plugin="Local.CustomMacro"/><Properties><Configuration/></Properties>'
              f'<EngineSettings Macro="{nested}"/></Node>') if nested else (
        '<Node ToolID="2"><GuiSettings Plugin="AlteryxBasePluginsGui.Formula.Formula"/><Properties><Configuration>'
        '<FormulaFields><FormulaField field="amount" type="Int64" size="8" expression="[amount] * 2"/>'
        '</FormulaFields></Configuration></Properties></Node>')
    return ('<AlteryxDocument><Nodes><Node ToolID="1"><GuiSettings Plugin="AlteryxBasePluginsGui.MacroInput.MacroInput"/>'
            '<Properties><Configuration><Name>Input</Name></Configuration></Properties></Node>' + middle +
            '<Node ToolID="3"><GuiSettings Plugin="AlteryxBasePluginsGui.MacroOutput.MacroOutput"/><Properties>'
            '<Configuration><Name>Output</Name></Configuration></Properties></Node></Nodes><Connections>'
            '<Connection><Origin ToolID="1" Connection="Output"/><Destination ToolID="2" Connection="Input"/></Connection>'
            '<Connection><Origin ToolID="2" Connection="Output"/><Destination ToolID="3" Connection="Input"/></Connection>'
            '</Connections><Properties><RuntimeProperties><ModuleType>Macro</ModuleType></RuntimeProperties></Properties></AlteryxDocument>')


def test_uploaded_nested_macro_runs_and_exports_through_canonical_paths(tmp_path):
    imported = import_macro({"name": "outer.yxmc", "xml": macro_xml("nested/inner.yxmc"),
                             "files": [{"name": "nested/inner.yxmc", "xml": macro_xml()}]}, tmp_path)
    assert imported["tool"]["inputs"] == ["Input"] and imported["tool"]["outputs"] == ["Output"]
    graph = simple_graph()
    tool = imported["tool"]
    graph["nodes"].append({"id": "80", "type": tool["type"], "config": tool["defaults"], "inputs": tool["inputs"], "outputs": tool["outputs"]})
    graph["nodes"].append({"id": "99", "type": "DbFileOutput", "config": {"file": "macro-result.csv"}})
    graph["edges"] = [{"from": "42", "to": "80"}, {"from": "80", "to": "99"}]
    result = server._run(graph)
    assert result["runtimeStatus"] == "executed"
    assert next(p for p in result["previews"] if p["node"] == "80")["rows"] == [[4], [10]]
    assert result["phase2Status"] == "compiled", result["blockers"]
    assert "alteryx2python" not in result["python"]
    # Source remains editable even after its macro dependencies are embedded.
    saved = graph_from_xml(result["yxmd"], tmp_path)
    assert ET.fromstring(compile_graph_to_yxmd(saved)).find("Nodes/Node[@ToolID='80']/EngineSettings").get("Macro") == imported["path"]
    for member in imported["files"]:
        Path(member["path"]).unlink()
    namespace = {"__file__": str(tmp_path / "exported.py")}
    exec(result["python"], namespace)
    namespace["run_workflow"](input_dir=tmp_path, output_dir=tmp_path / "native")
    assert pd.read_csv(tmp_path / "native/macro-result.csv")["amount"].tolist() == [4, 10]


@pytest.mark.parametrize("name", ["../evil.yxmc", "C:/evil.yxmc", "/evil.yxmc", "nested/../../evil.yxmc", "wrong.yxmd"])
def test_macro_upload_rejects_unsafe_paths_before_writing(tmp_path, name):
    with pytest.raises(ValueError):
        import_macro({"name": name, "xml": macro_xml()}, tmp_path)
    assert not list(tmp_path.iterdir())


def test_imported_unknown_tool_can_roundtrip_but_never_fake_a_runtime_result(tmp_path):
    root = ET.fromstring(compile_graph_to_yxmd(simple_graph()))
    root.find("Nodes/Node/GuiSettings").set("Plugin", "Vendor.UnknownCustomTool")
    graph = graph_from_xml(ET.tostring(root, encoding="unicode"), tmp_path)
    assert shape(ET.fromstring(compile_graph_to_yxmd(graph))) == shape(root)
    with pytest.raises(ApiError, match="No runtime implementation") as raised:
        server._run(graph)
    assert raised.value.code == "runtime_unavailable"


def test_mail_event_creates_downloadable_eml_without_smtp(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Draft profile must never open an SMTP connection")
    monkeypatch.setattr("smtplib.SMTP", forbidden)
    monkeypatch.setattr("smtplib.SMTP_SSL", forbidden)
    graph = simple_graph()
    graph["eventsXml"] = ('<Events><Event><When>AfterNoError</When><SendMail>True</SendMail>'
                          '<email_From>from@example.invalid</email_From><email_To>to@example.invalid</email_To>'
                          '<email_Subject>Completed</email_Subject><email_Body>Report body</email_Body></Event></Events>')
    result = server._run(graph)
    event = next(item for item in result["diagnostics"] if item.get("kind") == "workflow_event")
    assert event["sent"] is False
    artifact = next(item for item in result["artifacts"] if item["name"] == "event-0.eml")
    message = BytesParser(policy=policy.default).parsebytes(base64.b64decode(artifact["content"]))
    assert message["Subject"] == "Completed" and message["X-Unsent"] == "1"
    assert result["phase2Status"] == "compiled", result["blockers"]


def test_event_commands_are_denied_by_default_and_only_run_explicit_fixture(tmp_path):
    graph = simple_graph()
    graph["sourcePath"] = str(tmp_path / "workflow.yxmd")
    events = ET.Element("Events")
    event = ET.SubElement(events, "Event")
    for key, value in {"When": "BeforeRun", "cmd_Program": sys.executable,
                       "cmd_CommandArguments": '-c "from pathlib import Path; Path(\'fixture.txt\').write_text(\'explicit\')"'}.items():
        ET.SubElement(event, key).text = value
    graph["eventsXml"] = ET.tostring(events, encoding="unicode")
    with pytest.raises(ApiError) as raised:
        server._run(graph)
    assert raised.value.code == "permission_denied"
    assert not (tmp_path / "fixture.txt").exists()
    graph["runtime"] = {"allowed_commands": [sys.executable], "event_working_dir": str(tmp_path)}
    result = server._run(graph)
    assert (tmp_path / "fixture.txt").read_text() == "explicit"
    assert any(d.get("status") == "success" for d in result["diagnostics"])


def test_runcommand_never_silently_returns_passthrough(tmp_path):
    graph = simple_graph()
    engine = '<EngineSettings EngineDll="AlteryxBasePluginsEngine.dll" EngineDllEntryPoint="AlteryxRunCommand"/>'
    graph["nodes"].append({"id": "55", "type": "RunCommand", "inputs": ["Input"], "outputs": ["Output"], "config": {
        "configurationXml": '<Configuration><ProgramName>unapproved.exe</ProgramName><Arguments>--test</Arguments></Configuration>',
        "engineSettingsXml": engine}})
    graph["edges"] = [{"from": "42", "to": "55"}]
    with pytest.raises(ApiError) as raised:
        server._run(graph)
    assert raised.value.code == "permission_denied"


def test_python_tool_stdout_is_returned_alongside_real_output(tmp_path):
    graph = simple_graph()
    config = ET.Element("Configuration")
    ET.SubElement(config, "productionModeScript").text = "from ayx import Alteryx\nprint('tool-log')\ndata = Alteryx.read('#1')\nAlteryx.write(data, 1)"
    graph["nodes"].append({"id": "60", "type": "JupyterCode", "inputs": ["Input"], "outputs": ["Output"],
                           "config": {"configurationXml": ET.tostring(config, encoding="unicode")}})
    graph["edges"] = [{"from": "42", "to": "60"}]
    result = server._run(graph)
    assert result["stdout"] == "tool-log\n"
    assert result["previews"][-1]["rows"] == [[2], [5]]


@pytest.fixture
def api_server(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "WEBAPP_DIR", tmp_path)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.EditorHandler)
    thread = Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    httpd.server_close()
    thread.join(timeout=5)


def request_json(url, payload=None):
    request = Request(url, data=json.dumps(payload).encode() if payload is not None else None,
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=20) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def test_http_workflow_import_compile_run_and_typed_validation(api_server):
    status, imported = request_json(api_server + "/api/workflow/import", {"name": "source.yxmd", "xml": compile_graph_to_yxmd(simple_graph())})
    assert status == 200 and imported["graph"]["workflowXml"] == imported["workflowXml"]
    status, compiled = request_json(api_server + "/api/compile", imported["graph"])
    assert status == 200 and compiled["phase2Status"] == "compiled"
    status, ran = request_json(api_server + "/api/run", imported["graph"])
    assert status == 200 and ran["rows"] == [[2], [5]]
    bad = {**imported["graph"], "runtime": {"allowed_commands": "*"}}
    status, error = request_json(api_server + "/api/run", bad)
    assert status == 400 and error["code"] == "invalid_configuration" and "trace" not in error
    status, error = request_json(api_server + "/api/workflow/import", {"name": "bad.yxwz", "xml": "<broken"})
    assert status == 400 and error["errorType"] == "ParseError"


def test_http_macro_bundle_and_existing_data_import(api_server):
    status, imported = request_json(api_server + "/api/macros/import", {"name": "test.yxmc", "xml": macro_xml()})
    assert status == 200 and Path(imported["path"]).is_file()
    status, data = request_json(api_server + "/api/import", {"name": "data.csv", "content": base64.b64encode(b"A\n1\n").decode()})
    assert status == 200 and data["rows"] == [["1"]]


def test_sparse_source_and_both_engine_locations_roundtrip_without_added_nodes(tmp_path):
    source = ('<AlteryxDocument><Nodes><Node ToolID="1"><GuiSettings Plugin="Vendor.Unknown"/>'
              '<Properties><EngineSettings Macro="chosen.yxmc" custom="yes"/></Properties>'
              '<EngineSettings Macro="secondary.yxmc" custom="also-keep"/></Node>'
              '<Node ToolID="2"/></Nodes><Connections/><Properties keep="yes"/></AlteryxDocument>')
    graph = graph_from_xml(source, tmp_path)
    assert "chosen.yxmc" in graph["nodes"][0]["config"]["engineSettingsXml"]
    assert shape(ET.fromstring(compile_graph_to_yxmd(graph))) == shape(ET.fromstring(source))


@pytest.mark.parametrize("kind", ["Action", "QuestionTextBox"])
def test_unbound_interface_nodes_are_blocked_instead_of_discarded(kind):
    graph = {"nodes": [{"id": "1", "type": kind, "config": {"configurationXml": "<Configuration />"}}], "edges": []}
    compiled = server._compile(graph)
    assert compiled["phase2Status"] == "blocked" and compiled["python"] == ""
    assert "RuntimeProperties" in compiled["blockers"][0]["message"]
    with pytest.raises(ApiError) as raised:
        server._run(graph)
    assert raised.value.code == "configuration_binding_missing"


def test_runtime_can_execute_structural_action_without_silent_phase_two_freezing(tmp_path):
    root = ET.fromstring(app_xml())
    action = root.find("Properties/RuntimeProperties/Actions/NoCondition/True/Action")
    action.find("Type").text = "EditExpression"
    ET.SubElement(action, "Expression").text = '"[amount] > 4"'
    graph = graph_from_xml(ET.tostring(root, encoding="unicode"), tmp_path)
    result = server._run(graph)
    assert result["runtimeStatus"] == "executed" and result["phase2Status"] == "blocked"
    assert result["python"] == "" and result["blockers"][0]["code"] == "phase2_unsupported"
    assert next(p for p in result["previews"] if p["node"] == "2" and p["anchor"] == "True")["rows"] == [[5]]
    graph["parameterMode"] = "specialized"
    specialized = server._compile(graph)
    assert specialized["phase2Status"] == "compiled" and specialized["manifest"]["parameter_mode"] == "specialized"


def test_html_report_artifact_is_real_content_and_sink_is_isolated(tmp_path):
    graph = simple_graph()
    graph["nodes"].extend([
        {"id": "50", "type": "PortfolioComposerTable", "config": {"configurationXml": "<Configuration><TableMode>Basic</TableMode></Configuration>"}},
        {"id": "60", "type": "PortfolioComposerRender", "config": {"configurationXml": f"<Configuration><TempFileType>html</TempFileType><OutputFile>{(tmp_path / 'report.html').as_posix()}</OutputFile><DataField>Report</DataField></Configuration>"}},
    ])
    graph["edges"] = [{"from": "42", "to": "50"}, {"from": "50", "to": "60"}]
    result = server._run(graph)
    artifact = next(item for item in result["artifacts"] if item["name"] == "report.html")
    content = base64.b64decode(artifact["content"]).decode()
    assert "<table" in content and "amount" in content and ">2<" in content and ">5<" in content
    assert not (tmp_path / "report.html").exists()


def test_python_tool_palette_and_import_expose_numbered_ports(tmp_path):
    tool = next(item for item in server.EDITOR_TOOLS if item["type"] == "JupyterCode")
    assert tool["inputs"] == ["Input", "Input2", "Input3", "Input4", "Input5"]
    assert tool["outputs"] == ["Output", "Output2", "Output3", "Output4", "Output5"]
    graph = {"nodes": [{"id": "7", "type": "JupyterCode", "config": tool["defaults"]}], "edges": []}
    imported = graph_from_xml(compile_graph_to_yxmd(graph), tmp_path)
    assert imported["nodes"][0]["outputs"] == tool["outputs"]
    assert imported["nodes"][0]["inputs"] == tool["inputs"]


@pytest.mark.parametrize("batch", [False, True])
def test_macro_required_answers_are_bound_by_caller_or_batch_rows(tmp_path, batch):
    root = ET.fromstring(macro_xml())
    root.find(".//FormulaField").set("expression", "[amount] * FACTOR")
    runtime = root.find("Properties/RuntimeProperties")
    question = ET.SubElement(ET.SubElement(runtime, "Questions"), "Question")
    for key, value in {"Type": "ControlParam" if batch else "NumericUpDown", "Name": "factor", "Required": "True"}.items():
        ET.SubElement(question, key).text = value
    action = ET.SubElement(ET.SubElement(ET.SubElement(ET.SubElement(runtime, "Actions"), "NoCondition"), "True"), "Action")
    for key, value in {"Type": "UpdateValueReplace", "Variable": "factor", "ReplaceText": "FACTOR",
                       "Destination": "2/FormulaFields/FormulaField/@expression"}.items():
        ET.SubElement(action, key).text = value
    if batch:
        ET.SubElement(ET.SubElement(runtime, "BatchMacro"), "OutputMode").text = "AllSame"
    imported = import_macro({"name": "required.yxmc", "xml": ET.tostring(root, encoding="unicode")}, tmp_path)
    tool = imported["tool"]
    graph = simple_graph()
    graph["nodes"].append({"id": "80", "type": tool["type"], "inputs": ["Input", "factor"] if batch else ["Input"],
                           "outputs": ["Output"], "config": {**tool["defaults"], "configurationXml":
                           '<Configuration><Value name="factor">' + ("coeff" if batch else "4") + '</Value></Configuration>'}})
    graph["edges"] = [{"from": "42", "to": "80"}]
    if batch:
        graph["nodes"].append({"id": "70", "type": "TextInput", "config": {"fields": ["coeff"], "rows": [["2"], ["3"]]}})
        graph["edges"].append({"from": "70", "to": "80", "toAnchor": "factor"})
    result = server._run(graph)
    assert next(p for p in result["previews"] if p["node"] == "80")["rows"] == ([[4], [10], [6], [15]] if batch else [[8], [20]])
    assert result["phase2Status"] == ("blocked" if batch else "compiled")


def test_imported_grouped_action_metadata_and_layout_do_not_require_node_ids(tmp_path):
    root = ET.fromstring(app_xml())
    nodes = root.find("Nodes")
    for tool_id, kind in (("90", "NumericUpDown"), ("91", "Action"), ("92", "QuestionTab")):
        node = ET.SubElement(nodes, "Node", ToolID=tool_id)
        ET.SubElement(node, "GuiSettings", Plugin=f"AlteryxGuiToolkit.Questions.{kind}.{kind}")
        ET.SubElement(ET.SubElement(node, "Properties"), "Configuration")
    result = server._run(graph_from_xml(ET.tostring(root, encoding="unicode"), tmp_path))
    assert result["runtimeStatus"] == "executed" and result["phase2Status"] == "compiled"
    graph = simple_graph()
    graph["nodes"].append({"id": "92", "type": "QuestionTab", "config": {"configurationXml": "<Configuration />"}})
    assert server._run(graph)["runtimeStatus"] == "executed"

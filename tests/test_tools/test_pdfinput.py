import pandas as pd

from alteryx2python.tools.pdfinput import PDFInputTool, pdfinput_tool


def test_pdfinput_passes_input_and_records_directory(workflow_context):
    frame = pd.DataFrame({"FileName": ["a.pdf"]})

    output = pdfinput_tool(
        {"Input": frame},
        {"pdf_directory": "docs", "base_dir": "E:/Automation/Alteryx2Python"},
        workflow_context,
    )["Output"]

    assert output["FileName"].tolist() == ["a.pdf"]
    assert output["PDFDirectory"].str.endswith("docs").all()
    trace = workflow_context.traces[-1].to_dict()
    assert trace["config"]["pdf_read_performed"] is False


def test_pdfinput_tool_class_executes_same_contract(workflow_context):
    result = PDFInputTool().execute({}, {}, workflow_context)

    assert "PDFDirectory" in result["Output"].columns

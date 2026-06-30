import pandas as pd

from alteryx2python.tools.pdftotext import PDFToTextTool, pdftotext_tool


def test_pdftotext_passes_existing_data_input_without_ocr(workflow_context):
    frame = pd.DataFrame({"Path": ["a.pdf"], "Text": ["existing"]})

    output = pdftotext_tool({"Data Input": frame}, {"language": "EN"}, workflow_context)["Output"]

    pd.testing.assert_frame_equal(output, frame)
    trace = workflow_context.traces[-1].to_dict()
    assert trace["tool_type"] == "PDFToText"
    assert trace["config"]["pdf_text_extraction_performed"] is False


def test_pdftotext_emits_metadata_row_without_input(workflow_context):
    output = pdftotext_tool(
        {},
        {"path_input_value": "sample.pdf", "base_dir": "E:/Automation/Alteryx2Python"},
        workflow_context,
    )["Output"]

    assert output.loc[0, "File"] == "sample.pdf"
    assert output.loc[0, "Output Option"] == "metadata_only"


def test_pdftotext_tool_class_executes_same_contract(workflow_context):
    result = PDFToTextTool().execute({}, {}, workflow_context)

    assert "Text" in result["Output"].columns

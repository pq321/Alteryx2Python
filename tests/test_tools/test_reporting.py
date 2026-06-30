import pandas as pd

from alteryx2python.tools.reporting import (
    alteryxreportchartgui_tool,
    overlay_tool,
    plotlycharting_tool,
    portfoliocomposerlayout_tool,
    portfoliocomposerrender_tool,
    portfoliocomposertable_tool,
    portfoliocomposertext_tool,
    reportfooter_tool,
    reportheader_tool,
    reportlegendbuilder_tool,
    reportlegendsplitter_tool,
    reportmap_tool,
    visuallayout_tool,
)


def test_report_fragment_tools_emit_output_report_payload(workflow_context):
    input_frame = pd.DataFrame({"City": ["New York", "Boston"], "Sales": [10, 20]})

    for tool_type, tool in [
        ("PortfolioComposerText", portfoliocomposertext_tool),
        ("PortfolioComposerTable", portfoliocomposertable_tool),
        ("PortfolioComposerLayout", portfoliocomposerlayout_tool),
        ("ReportMap", reportmap_tool),
        ("PlotlyCharting", plotlycharting_tool),
        ("AlteryxReportChartGui", alteryxreportchartgui_tool),
        ("Overlay", overlay_tool),
        ("VisualLayout", visuallayout_tool),
    ]:
        result = tool({"Input": input_frame}, {"sample": tool_type}, workflow_context)

        assert set(result) == {"Output"}
        assert result["Output"].loc[0, "report_type"] == tool_type
        assert result["Output"].loc[0, "source_rows"] == 2
        assert result["Output"].loc[0, "source_columns"] == ["City", "Sales"]


def test_report_text_without_input_still_emits_report_fragment(workflow_context):
    result = portfoliocomposertext_tool({}, {"output_field": "Title"}, workflow_context)

    assert result["Output"].loc[0, "report_type"] == "PortfolioComposerText"
    assert result["Output"].loc[0, "source_rows"] == 0


def test_report_render_records_sink_without_outputs(workflow_context):
    result = portfoliocomposerrender_tool(
        {"Input": pd.DataFrame({"Report": ["fragment"]})},
        {"temp_file_type": "pdf", "output_file": "%Temp%/Output.pdf"},
        workflow_context,
    )

    assert result == {}
    assert workflow_context.traces[-1].tool_type == "PortfolioComposerRender"
    assert workflow_context.traces[-1].config["report_config"]["temp_file_type"] == "pdf"


def test_report_header_uses_output13_anchor(workflow_context):
    result = reportheader_tool(
        {"Report Layout": pd.DataFrame({"Report": ["body"]})},
        {"header_text": "Header"},
        workflow_context,
    )

    assert set(result) == {"Output13"}
    assert result["Output13"].loc[0, "report_type"] == "ReportHeader"


def test_report_macro_fragment_tools_emit_output(workflow_context):
    for tool_type, tool in [
        ("ReportFooter", reportfooter_tool),
        ("ReportLegendSplitter", reportlegendsplitter_tool),
        ("ReportLegendBuilder", reportlegendbuilder_tool),
    ]:
        result = tool({"Input": pd.DataFrame({"Legend": ["A"]})}, {}, workflow_context)

        assert set(result) == {"Output"}
        assert result["Output"].loc[0, "report_type"] == tool_type

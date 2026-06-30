from __future__ import annotations

import json
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _input_schemas(inputs: dict[str, pd.DataFrame]) -> dict[str, object]:
    return {
        anchor: snapshot_schema(frame)
        for anchor, frame in inputs.items()
        if isinstance(frame, pd.DataFrame)
    }


def _first_input(inputs: dict[str, pd.DataFrame]) -> pd.DataFrame | None:
    for frame in inputs.values():
        if isinstance(frame, pd.DataFrame):
            return frame
    return None


def _row_count(inputs: dict[str, pd.DataFrame]) -> int:
    frame = _first_input(inputs)
    return 0 if frame is None else len(frame.index)


def _config_summary(config: dict[str, Any]) -> str:
    summary = {
        key: value
        for key, value in config.items()
        if key not in {"node_id", "source_tool_id", "base_dir"}
    }
    return json.dumps(summary, default=str, sort_keys=True)


def _fragment_frame(tool_type: str, config: dict[str, Any], inputs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    frame = _first_input(inputs)
    source_columns = [] if frame is None else list(frame.columns)
    return pd.DataFrame(
        [
            {
                "Report": f"{tool_type} report fragment",
                "report_type": tool_type,
                "source_rows": _row_count(inputs),
                "source_columns": source_columns,
                "config": _config_summary(config),
            }
        ]
    )


def _record_report_node(
    *,
    tool_type: str,
    inputs: dict[str, pd.DataFrame],
    outputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=tool_type,
        source_tool_id=config.get("source_tool_id"),
        inputs={key: value for key, value in inputs.items() if isinstance(value, pd.DataFrame)},
        outputs=outputs,
        status="success",
        config={
            "node_id": config.get("node_id"),
            "source_tool_id": config.get("source_tool_id"),
            "input_schemas": _input_schemas(inputs),
            "report_config": {
                key: value
                for key, value in config.items()
                if key not in {"node_id", "source_tool_id"}
            },
        },
    )
    return outputs


def _report_fragment_tool(
    tool_type: str,
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
    output_anchor: str = "Output",
) -> dict[str, pd.DataFrame]:
    outputs = {output_anchor: _fragment_frame(tool_type, config, inputs)}
    return _record_report_node(
        tool_type=tool_type,
        inputs=inputs,
        outputs=outputs,
        config=config,
        context=context,
    )


def portfoliocomposertext_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("PortfolioComposerText", inputs, config, context)


def portfoliocomposertable_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("PortfolioComposerTable", inputs, config, context)


def portfoliocomposerimage_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("PortfolioComposerImage", inputs, config, context)


def portfoliocomposerlayout_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("PortfolioComposerLayout", inputs, config, context)


def reportmap_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("ReportMap", inputs, config, context)


def plotlycharting_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("PlotlyCharting", inputs, config, context)


def alteryxreportchartgui_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("AlteryxReportChartGui", inputs, config, context)


def visuallayout_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("VisualLayout", inputs, config, context)


def overlay_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("Overlay", inputs, config, context)


def reportheader_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("ReportHeader", inputs, config, context, "Output13")


def reportfooter_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("ReportFooter", inputs, config, context)


def reportlegendsplitter_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("ReportLegendSplitter", inputs, config, context)


def reportlegendbuilder_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _report_fragment_tool("ReportLegendBuilder", inputs, config, context)


def portfoliocomposerrender_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    return _record_report_node(
        tool_type="PortfolioComposerRender",
        inputs=inputs,
        outputs={},
        config=config,
        context=context,
    )


class PortfolioComposerTextTool(BaseTool):
    tool_type = "PortfolioComposerText"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return portfoliocomposertext_tool(inputs, config, context)


class PortfolioComposerTableTool(BaseTool):
    tool_type = "PortfolioComposerTable"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return portfoliocomposertable_tool(inputs, config, context)


class PortfolioComposerImageTool(BaseTool):
    tool_type = "PortfolioComposerImage"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return portfoliocomposerimage_tool(inputs, config, context)


class PortfolioComposerLayoutTool(BaseTool):
    tool_type = "PortfolioComposerLayout"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return portfoliocomposerlayout_tool(inputs, config, context)


class PortfolioComposerRenderTool(BaseTool):
    tool_type = "PortfolioComposerRender"
    input_anchors = ("Input",)
    output_anchors = ()

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return portfoliocomposerrender_tool(inputs, config, context)


class ReportMapTool(BaseTool):
    tool_type = "ReportMap"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return reportmap_tool(inputs, config, context)


class PlotlyChartingTool(BaseTool):
    tool_type = "PlotlyCharting"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return plotlycharting_tool(inputs, config, context)


class AlteryxReportChartGuiTool(BaseTool):
    tool_type = "AlteryxReportChartGui"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return alteryxreportchartgui_tool(inputs, config, context)


class VisualLayoutTool(BaseTool):
    tool_type = "VisualLayout"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return visuallayout_tool(inputs, config, context)


class OverlayTool(BaseTool):
    tool_type = "Overlay"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return overlay_tool(inputs, config, context)


class ReportHeaderTool(BaseTool):
    tool_type = "ReportHeader"
    input_anchors = ("Report Layout",)
    output_anchors = ("Output13",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return reportheader_tool(inputs, config, context)


class ReportFooterTool(BaseTool):
    tool_type = "ReportFooter"
    input_anchors = ("Report Layout",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return reportfooter_tool(inputs, config, context)


class ReportLegendSplitterTool(BaseTool):
    tool_type = "ReportLegendSplitter"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return reportlegendsplitter_tool(inputs, config, context)


class ReportLegendBuilderTool(BaseTool):
    tool_type = "ReportLegendBuilder"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return reportlegendbuilder_tool(inputs, config, context)

from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def parse_alteryx_report_chart_config(raw_config: dict[str, Any]) -> ToolParserResult:
    general_styles = attributes(child(raw_config, "GeneralStyles"))
    return ToolParserResult(
        normalized_config={
            "chart_type": text(child(raw_config, "ChartType"), ""),
            "label_field": text(child(raw_config, "LabelField"), ""),
            "chart_title": str(general_styles.get("ChartTitle", "")),
            "chart_width": str(general_styles.get("ChartSizeW", "")),
            "chart_height": str(general_styles.get("ChartSizeH", "")),
        }
    )


def parse_visual_layout_config(raw_config: dict[str, Any]) -> ToolParserResult:
    layout_fields = child(raw_config, "LayoutFields")
    document = child(layout_fields, "Document")
    return ToolParserResult(
        normalized_config={
            "temp_file_type": text(child(document, "TempFileType"), ""),
            "render_type": text(child(document, "RenderType"), ""),
            "num_incoming_connections": text(child(layout_fields, "NumIncomingConnections"), ""),
            "allow_resizing": text(child(layout_fields, "AllowResizing"), ""),
            "can_join": text(child(layout_fields, "CanJoin"), ""),
        }
    )


def parse_overlay_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "field_base": text(child(raw_config, "Field_Base"), ""),
            "field_tl": text(child(raw_config, "Field_TL"), ""),
            "field_tc": text(child(raw_config, "Field_TC"), ""),
            "field_tr": text(child(raw_config, "Field_TR"), ""),
            "field_ml": text(child(raw_config, "Field_ML"), ""),
            "field_mc": text(child(raw_config, "Field_MC"), ""),
            "field_mr": text(child(raw_config, "Field_MR"), ""),
            "field_ll": text(child(raw_config, "Field_LL"), ""),
            "field_lc": text(child(raw_config, "Field_LC"), ""),
            "field_lr": text(child(raw_config, "Field_LR"), ""),
            "padding": attributes(child(raw_config, "Padding")),
            "preserve_source_fields": str(
                attributes(child(raw_config, "PreserveSourceFields")).get("value", "False")
            ).lower()
            == "true",
        }
    )

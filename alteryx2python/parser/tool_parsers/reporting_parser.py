from __future__ import annotations

from typing import Any

from alteryx2python.parser.tool_parsers.common import ToolParserResult, as_list, attributes, child, text


def _value_map(raw_config: dict[str, Any]) -> dict[str, str]:
    values: dict[str, str] = {}
    for value in as_list(child(raw_config, "Value")):
        name = attributes(value).get("name")
        if name:
            values[str(name)] = text(value)
    return values


def _bool_attr(node: Any, key: str = "value") -> bool | None:
    value = attributes(node).get(key)
    if value is None:
        return None
    return str(value).strip().lower() == "true"


def _field_names(node: Any, *, selected_only: bool = False) -> list[str]:
    names: list[str] = []
    for field in as_list(child(node, "Field")):
        attrs = attributes(field)
        if selected_only and str(attrs.get("selected", "True")).lower() == "false":
            continue
        name = attrs.get("name") or attrs.get("field")
        if name:
            names.append(str(name))
    return names


def parse_report_text_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "output_field": text(child(raw_config, "Output"), "Report"),
            "header_field": text(child(raw_config, "HeaderField"), ""),
            "header_mode": _bool_attr(child(raw_config, "HeaderMode")),
            "raw_mode": _bool_attr(child(raw_config, "RawMode")),
            "rich_text_mode": _bool_attr(child(raw_config, "RichTextMode")),
            "message": text(child(raw_config, "Message"), ""),
            "rich_text": text(child(raw_config, "RichTextString"), ""),
        }
    )


def parse_report_table_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "table_mode": text(child(raw_config, "TableMode"), "Basic"),
            "width": text(child(raw_config, "Width"), ""),
            "show_header": _bool_attr(child(raw_config, "ShowHeader")),
            "show_bar_graph": _bool_attr(child(raw_config, "ShowBarGraph")),
            "bar_graph_field": text(child(raw_config, "BarGraphField"), ""),
            "table_fields": _field_names(child(raw_config, "TableFields"), selected_only=True),
            "pivot_table_fields": _field_names(child(raw_config, "PivotTableFields"), selected_only=True),
            "grouping_fields": _field_names(child(raw_config, "GroupingFields")),
            "pivot_mode": text(child(raw_config, "PivotMode"), ""),
        }
    )


def parse_report_image_config(raw_config: dict[str, Any]) -> ToolParserResult:
    encoded = text(child(raw_config, "EncodedImage"), "")
    return ToolParserResult(
        normalized_config={
            "image_mode": text(child(raw_config, "ImageMode"), ""),
            "filename": text(child(raw_config, "Filename"), ""),
            "modify_filename": _bool_attr(child(raw_config, "ModifyFilename")),
            "modify_mode": text(child(raw_config, "ModifyMode"), ""),
            "modify_field": text(child(raw_config, "ModifyField"), ""),
            "stop_if_not_found": _bool_attr(child(raw_config, "StopIfNotFound")),
            "has_encoded_image": bool(encoded),
            "image_style": attributes(child(raw_config, "ImageStyle")),
        }
    )


def parse_report_layout_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "orientation": text(child(raw_config, "Orientation"), ""),
            "layout_fields": _field_names(child(raw_config, "LayoutFields"), selected_only=True),
            "grouping_fields": _field_names(child(raw_config, "GroupingFields")),
            "grouping_mode": text(child(raw_config, "GroupingMode"), ""),
            "section_name_for_all_records": text(child(raw_config, "SectionNameForAllRecords"), ""),
            "section_name_for_group": text(child(raw_config, "SectionNameForGroup"), ""),
            "separator": text(child(raw_config, "Separator"), ""),
            "width": text(child(raw_config, "Width"), ""),
            "height": text(child(raw_config, "Height"), ""),
        }
    )


def parse_report_render_config(raw_config: dict[str, Any]) -> ToolParserResult:
    return ToolParserResult(
        normalized_config={
            "temp_file_type": text(child(raw_config, "TempFileType"), ""),
            "output_file": text(child(raw_config, "OutputFile"), ""),
            "batch_mode": _bool_attr(child(raw_config, "BatchMode")),
            "data_field": text(child(raw_config, "DataField"), ""),
            "group_field": text(child(raw_config, "GroupField"), ""),
            "filename_modifier": text(child(raw_config, "FilenameModifier"), ""),
            "show_header": _bool_attr(child(raw_config, "ShowHeader")),
            "show_footer": _bool_attr(child(raw_config, "ShowFooter")),
            "header_field": text(child(raw_config, "HeaderField"), ""),
            "footer_field": text(child(raw_config, "FooterField"), ""),
            "portrait_mode": _bool_attr(child(raw_config, "PortraitMode")),
        }
    )


def parse_report_map_config(raw_config: dict[str, Any]) -> ToolParserResult:
    layers = child(child(raw_config, "Layers"), "Layer")
    return ToolParserResult(
        normalized_config={
            "reference_map": text(child(raw_config, "ReferenceMap"), ""),
            "image_width": text(child(raw_config, "ImageWidth"), ""),
            "image_height": text(child(raw_config, "ImageHeight"), ""),
            "image_resolution": text(child(raw_config, "ImageResolution"), ""),
            "scale_units": text(child(raw_config, "ScaleUnits"), ""),
            "is_metric": _bool_attr(child(raw_config, "IsMetric")),
            "legend": child(raw_config, "Legend"),
            "layer_count": len(as_list(layers)),
        }
    )


def parse_plotly_charting_config(raw_config: dict[str, Any]) -> ToolParserResult:
    charting_fields = child(raw_config, "ChartingFields")
    traces = as_list(child(charting_fields, "Traces"))
    return ToolParserResult(
        normalized_config={
            "trace_count": len(traces),
            "traces": [
                {
                    "type": text(child(trace, "type"), ""),
                    "mode": text(child(trace, "mode"), ""),
                    "name": text(child(trace, "name"), ""),
                    "x": text(child(trace, "xsrc"), ""),
                    "y": text(child(trace, "ysrc"), ""),
                }
                for trace in traces
                if isinstance(trace, dict)
            ],
            "layout": child(charting_fields, "Layout"),
        }
    )


def parse_report_header_config(raw_config: dict[str, Any]) -> ToolParserResult:
    values = _value_map(raw_config)
    return ToolParserResult(
        normalized_config={
            "header_text": values.get("HeaderText", ""),
            "include_date": values.get("IncludeDate", "").lower() == "true",
            "date_format": values.get("DateFormat", ""),
            "include_image": values.get("IncludeImage", "").lower() == "true",
            "alteryx_logo": values.get("AlteryxLogo", "").lower() == "true",
            "own_logo": values.get("OwnLogo", "").lower() == "true",
            "image_file": values.get("ImageFile", ""),
        }
    )


def parse_report_footer_config(raw_config: dict[str, Any]) -> ToolParserResult:
    values = _value_map(raw_config)
    return ToolParserResult(
        normalized_config={
            "copyright_text": values.get("CopyrightText", ""),
            "info_text": values.get("InfoText", ""),
            "page_numbers": values.get("PageNumbers", "").lower() == "true",
        }
    )


def parse_report_legend_splitter_config(raw_config: dict[str, Any]) -> ToolParserResult:
    values = _value_map(raw_config)
    return ToolParserResult(normalized_config={"legend_field": values.get("Legend Field", "")})


def parse_report_legend_builder_config(raw_config: dict[str, Any]) -> ToolParserResult:
    values = _value_map(raw_config)
    return ToolParserResult(
        normalized_config={
            "text_field": values.get("Text Field", ""),
            "image_field": values.get("Image Field", ""),
            "text_style_field": values.get("Text Style Field", ""),
            "image_style_field": values.get("Image Style Field", ""),
        }
    )

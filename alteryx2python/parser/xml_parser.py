from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from xml.etree import ElementTree

from alteryx2python.ir.models import AnchorIR, EdgeIR, NodeIR, WorkflowIR
from alteryx2python.parser.base_parser import BaseWorkflowParser
from alteryx2python.parser.tool_catalog import CATALOG, catalog_entry_for_plugin
from alteryx2python.parser.tool_parsers import (
    make_catalog_parser,
    make_ml_parser,
    parse_action_config,
    parse_catalog_config,
    parse_apioutput_config,
    parse_appendfields_config,
    parse_arrange_config,
    parse_autofield_config,
    parse_basicdataprofile_config,
    parse_blobconvert_config,
    parse_blobinput_config,
    parse_bloboutput_config,
    parse_buffer_config,
    parse_calgarycrosscount_config,
    parse_calgarycrosscountappend_config,
    parse_calgaryinput_config,
    parse_calgaryjoin_config,
    parse_calgaryloader_config,
    parse_cass_config,
    parse_cassparse_config,
    parse_zip9coder_config,
    parse_condition_config,
    parse_createpoints_config,
    parse_dbfileinput_config,
    parse_dbfileoutput_config,
    parse_detour_config,
    parse_detourend_config,
    parse_download_config,
    parse_crosstab_config,
    parse_datacleansepro_config,
    parse_datacleansing_config,
    parse_datetime_config,
    parse_datetimenow_config,
    parse_dynamicinput_config,
    parse_dynamicrename_config,
    parse_dynamicselect_config,
    parse_distance_config,
    parse_directory_config,
    parse_error_config,
    parse_expectequal_config,
    parse_filter_config,
    parse_fieldinfo_config,
    parse_findnearest_config,
    parse_findreplace_config,
    parse_formula_config,
    parse_fuzzymatch_config,
    parse_geocoder_config,
    parse_join_config,
    parse_joinmultiple_config,
    parse_alteryx_report_chart_config,
    parse_interface_layout_config,
    parse_interface_value_config,
    parse_jsonparse_config,
    parse_jupytercode_config,
    parse_overlay_config,
    parse_generaterows_config,
    parse_generalize_config,
    parse_makecolumns_config,
    parse_makegrid_config,
    parse_makegroup_config,
    parse_macroinput_config,
    parse_macrooutput_config,
    parse_mapinput_config,
    parse_multifieldformula_config,
    parse_multirowformula_config,
    parse_pearsoncorrelation_config,
    parse_pdfinput_config,
    parse_pdftotext_config,
    parse_polybuild_config,
    parse_polysplit_config,
    parse_recordid_config,
    parse_rank_config,
    parse_regex_config,
    parse_plotly_charting_config,
    parse_report_image_config,
    parse_report_layout_config,
    parse_report_footer_config,
    parse_report_header_config,
    parse_report_legend_builder_config,
    parse_report_legend_splitter_config,
    parse_report_map_config,
    parse_report_render_config,
    parse_report_table_config,
    parse_report_text_config,
    parse_runningtotal_config,
    parse_runcommand_config,
    parse_sample_config,
    parse_select_config,
    parse_spatialinfo_config,
    parse_spatialmatch_config,
    parse_smooth_config,
    parse_spatialprocess_config,
    parse_sort_config,
    parse_summarize_config,
    parse_test_config,
    parse_textinput_config,
    parse_texttocolumns_config,
    parse_throttle_config,
    parse_tile_config,
    parse_tradearea_config,
    parse_transpose_config,
    parse_union_config,
    parse_unique_config,
    parse_visual_layout_config,
    parse_xmlparse_config,
    parse_dynamicreplace_config,
)
from alteryx2python.parser.tool_parsers.canvas_parser import (
    parse_blockuntildone_config,
    parse_controlcontainer_config,
    parse_htmlbox_config,
    parse_message_config,
    parse_textbox_config,
    parse_toolcontainer_config,
)


INPUT_ANCHOR_HINTS = {
    "Action",
    "Input",
    "Input2",
    "Join",
    "Left",
    "Question",
    "Right",
    "Targets",
}

INTERFACE_PLUGIN_PREFIX = "AlteryxGuiToolkit.Questions."
ACTION_PLUGIN = "AlteryxGuiToolkit.Action.Action"
CONTAINER_PLUGIN = "AlteryxGuiToolkit.ToolContainer.ToolContainer"
DOWNLOAD_PLUGIN = "AlteryxConnectorGui.Download.Download"
INTERFACE_BASELINE_PLUGINS = {
    "AlteryxGuiToolkit.Questions.CheckBoxGroup.CheckBoxGroup",
    "AlteryxGuiToolkit.Questions.Date.Date",
    "AlteryxGuiToolkit.Questions.DropDownListBox.DropDown",
    "AlteryxGuiToolkit.Questions.DropDownListBox.ListBox",
    "AlteryxGuiToolkit.Questions.FileBrowse.FileBrowse",
    "AlteryxGuiToolkit.Questions.FolderBrowse.FolderBrowse",
    "AlteryxGuiToolkit.Questions.Label.Label",
    "AlteryxGuiToolkit.Questions.LabelGroup.LabelGroup",
    "AlteryxGuiToolkit.Questions.Link.Link",
    "AlteryxGuiToolkit.Questions.Map.Map",
    "AlteryxGuiToolkit.Questions.NumericUpDown.NumericUpDown",
    "AlteryxGuiToolkit.Questions.RadioButtonGroup.RadioButtonGroup",
    "AlteryxGuiToolkit.Questions.Tab.Tab",
    "AlteryxGuiToolkit.Questions.TextBox.QuestionTextBox",
    "AlteryxGuiToolkit.Questions.Tree.Tree",
}
INTERFACE_CONFIG_TOOL_TYPES = {
    "CheckBoxGroup",
    "Date",
    "DropDown",
    "FolderBrowse",
    "Label",
    "LabelGroup",
    "Link",
    "ListBox",
    "Map",
    "NumericUpDown",
    "QuestionFileBrowse",
    "QuestionTab",
    "QuestionTextBox",
    "RadioButtonGroup",
    "Tree",
    "Condition",
}


def _normalize_tool_type(plugin_name: str) -> str:
    catalog_entry = catalog_entry_for_plugin(plugin_name)
    if catalog_entry is not None:
        return catalog_entry.tool_type
    if plugin_name == CONTAINER_PLUGIN:
        return "ToolContainer"
    if plugin_name == ACTION_PLUGIN:
        return "Action"
    if plugin_name == DOWNLOAD_PLUGIN:
        return "Download"
    if plugin_name.startswith(INTERFACE_PLUGIN_PREFIX):
        suffix = plugin_name.removeprefix(INTERFACE_PLUGIN_PREFIX)
        if suffix == "FileBrowse.FileBrowse":
            return "QuestionFileBrowse"
        if suffix == "TextBox.QuestionTextBox":
            return "QuestionTextBox"
        if suffix == "Tab.Tab":
            return "QuestionTab"
        return suffix.split(".")[-1]
    if plugin_name.startswith("AlteryxBasePluginsGui."):
        tail = plugin_name.split(".")[-1]
        if tail == "AlteryxSelect":
            return "Select"
        if tail == "JSONParse":
            return "JSONParse"
        if tail == "DbFileInput":
            return "DbFileInput"
        if tail == "DbFileOutput":
            return "DbFileOutput"
        return tail
    if plugin_name.startswith("AlteryxConnectorGui."):
        return plugin_name.split(".")[-1]
    return plugin_name.split(".")[-1] if plugin_name else "UNKNOWN"


def _normalize_macro_tool_type(macro_name: str) -> str | None:
    if not macro_name:
        return None
    if Path(macro_name).name.lower() == "cleanse.yxmc":
        return "DataCleansing"
    catalog_entry = catalog_entry_for_plugin(macro_name)
    if catalog_entry is None:
        catalog_entry = catalog_entry_for_plugin(Path(macro_name).name)
    if catalog_entry is not None and not catalog_entry.gui_only:
        return catalog_entry.tool_type
    stem = Path(macro_name).stem
    if stem:
        return f"Macro_{stem}"
    return None


def _normalize_config_only_tool_type(raw_config: dict[str, object]) -> str | None:
    values = raw_config.get("Value")
    if isinstance(values, dict):
        value_items = [values]
    elif isinstance(values, list):
        value_items = values
    else:
        return None
    names = {
        item.get("attributes", {}).get("name")
        for item in value_items
        if isinstance(item, dict) and isinstance(item.get("attributes"), dict)
    }
    if {
        "HeaderText",
        "IncludeDate",
        "DateFormat",
        "IncludeImage",
        "AlteryxLogo",
        "OwnLogo",
        "ImageFile",
    }.issubset(names):
        return "ReportHeader"
    if {"CopyrightText", "InfoText", "PageNumbers"}.issubset(names):
        return "ReportFooter"
    if {"Legend Field"}.issubset(names):
        return "ReportLegendSplitter"
    if {"Text Field", "Image Field", "Text Style Field", "Image Style Field"}.issubset(names):
        return "ReportLegendBuilder"
    if {"Number", "NNumber", "Percent", "NPercent"}.issubset(names):
        return "Sample"
    cleanse_names = {
        "List Box (11)",
        "Check Box (84)",
        "Check Box (117)",
        "Check Box (15)",
        "Check Box (109)",
        "Check Box (122)",
        "Check Box (53)",
        "Check Box (58)",
        "Check Box (70)",
        "Check Box (77)",
        "Drop Down (81)",
    }
    if cleanse_names.issubset(names):
        return "DataCleansing"
    return None


def _node_supported_status(plugin_name: str) -> tuple[str, str | None]:
    if plugin_name == CONTAINER_PLUGIN:
        return "L1_CONTAINER_ONLY", None
    if plugin_name == ACTION_PLUGIN:
        return "L1_PARSED_ONLY", None
    if plugin_name == DOWNLOAD_PLUGIN:
        return "L1_PARSED_ONLY", None
    if plugin_name in INTERFACE_BASELINE_PLUGINS:
        return "L1_PARSED_ONLY", None
    if plugin_name.startswith(INTERFACE_PLUGIN_PREFIX):
        return "L0_DEFERRED_INTERFACE_NODE", "Deferred interface node requires app/question semantics"
    if plugin_name.startswith("AlteryxConnectorGui."):
        return "L0_DEFERRED_CONNECTOR_NODE", "Deferred connector node requires external service semantics"
    return "L1_PARSED_ONLY", None


def _element_to_dict(element: ElementTree.Element) -> dict[str, object]:
    data: dict[str, object] = {}
    if element.attrib:
        data["attributes"] = dict(element.attrib)
    text = element.text or ""
    if element.tag != "c":
        text = text.strip()
    if text:
        data["text"] = text
    children = list(element)
    if children:
        grouped: dict[str, list[dict[str, object]]] = {}
        for child in children:
            grouped.setdefault(child.tag, []).append(_element_to_dict(child))
        for tag, entries in grouped.items():
            data[tag] = entries if len(entries) > 1 else entries[0]
    return data


TOOL_PARSERS = {
    "Action": parse_action_config,
    "AppendFields": parse_appendfields_config,
    "AlteryxReportChartGui": parse_alteryx_report_chart_config,
    "APIOutput": parse_apioutput_config,
    "Arrange": parse_arrange_config,
    "AutoField": parse_autofield_config,
    "BasicDataProfile": parse_basicdataprofile_config,
    "BlobConvert": parse_blobconvert_config,
    "BlobInput": parse_blobinput_config,
    "BlobOutput": parse_bloboutput_config,
    "Buffer": parse_buffer_config,
    "Condition": parse_condition_config,
    "CreatePoints": parse_createpoints_config,
    "CrossTab": parse_crosstab_config,
    "DataCleansePro": parse_datacleansepro_config,
    "DataCleansing": parse_datacleansing_config,
    "DateTime": parse_datetime_config,
    "DateTimeNow": parse_datetimenow_config,
    "DbFileInput": parse_dbfileinput_config,
    "DbFileOutput": parse_dbfileoutput_config,
    "Detour": parse_detour_config,
    "DetourEnd": parse_detourend_config,
    "Distance": parse_distance_config,
    "Directory": parse_directory_config,
    "Download": parse_download_config,
    "DynamicInput": parse_dynamicinput_config,
    "DynamicReplace": parse_dynamicreplace_config,
    "DynamicRename": parse_dynamicrename_config,
    "DynamicSelect": parse_dynamicselect_config,
    "Error": parse_error_config,
    "ExpectEqual": parse_expectequal_config,
    "Filter": parse_filter_config,
    "FieldInfo": parse_fieldinfo_config,
    "FindNearest": parse_findnearest_config,
    "FindReplace": parse_findreplace_config,
    "Formula": parse_formula_config,
    "FuzzyMatch": parse_fuzzymatch_config,
    "CheckBoxGroup": parse_interface_value_config,
    "Date": parse_interface_value_config,
    "DropDown": parse_interface_value_config,
    "FolderBrowse": parse_interface_value_config,
    "Label": parse_interface_layout_config,
    "LabelGroup": parse_interface_layout_config,
    "Link": parse_interface_layout_config,
    "Join": parse_join_config,
    "JoinMultiple": parse_joinmultiple_config,
    "JSONParse": parse_jsonparse_config,
    "JupyterCode": parse_jupytercode_config,
    "ListBox": parse_interface_value_config,
    "Map": parse_interface_value_config,
    "GenerateRows": parse_generaterows_config,
    "Generalize": parse_generalize_config,
    "MakeColumns": parse_makecolumns_config,
    "MakeGrid": parse_makegrid_config,
    "MakeGroup": parse_makegroup_config,
    "MacroInput": parse_macroinput_config,
    "MapInput": parse_mapinput_config,
    "MultiFieldFormula": parse_multifieldformula_config,
    "MultiRowFormula": parse_multirowformula_config,
    "NumericUpDown": parse_interface_value_config,
    "Overlay": parse_overlay_config,
    "PearsonCorrelation": parse_pearsoncorrelation_config,
    "PDFInput": parse_pdfinput_config,
    "PDFToText": parse_pdftotext_config,
    "PolyBuild": parse_polybuild_config,
    "PolySplit": parse_polysplit_config,
    "PlotlyCharting": parse_plotly_charting_config,
    "PortfolioComposerImage": parse_report_image_config,
    "PortfolioComposerLayout": parse_report_layout_config,
    "PortfolioComposerRender": parse_report_render_config,
    "PortfolioComposerTable": parse_report_table_config,
    "PortfolioComposerText": parse_report_text_config,
    "QuestionFileBrowse": parse_interface_value_config,
    "QuestionTab": parse_interface_layout_config,
    "QuestionTextBox": parse_interface_value_config,
    "RadioButtonGroup": parse_interface_value_config,
    "Tree": parse_interface_value_config,
    "RecordID": parse_recordid_config,
    "Rank": parse_rank_config,
    "RegEx": parse_regex_config,
    "ReportFooter": parse_report_footer_config,
    "ReportHeader": parse_report_header_config,
    "ReportLegendBuilder": parse_report_legend_builder_config,
    "ReportLegendSplitter": parse_report_legend_splitter_config,
    "ReportMap": parse_report_map_config,
    "RunningTotal": parse_runningtotal_config,
    "RunCommand": parse_runcommand_config,
    "Sample": parse_sample_config,
    "Select": parse_select_config,
    "SpatialInfo": parse_spatialinfo_config,
    "SpatialMatch": parse_spatialmatch_config,
    "Smooth": parse_smooth_config,
    "SpatialProcess": parse_spatialprocess_config,
    "Sort": parse_sort_config,
    "Summarize": parse_summarize_config,
    "Test": parse_test_config,
    "TextInput": parse_textinput_config,
    "TextToColumns": parse_texttocolumns_config,
    "Throttle": parse_throttle_config,
    "Tile": parse_tile_config,
    "TradeArea": parse_tradearea_config,
    "Transpose": parse_transpose_config,
    "Union": parse_union_config,
    "Unique": parse_unique_config,
    "VisualLayout": parse_visual_layout_config,
    "XMLParse": parse_xmlparse_config,
    "BrowseV2": parse_catalog_config,
    "TextBox": parse_textbox_config,
    "ToolContainer": parse_toolcontainer_config,
    "ControlContainer": parse_controlcontainer_config,
    "HtmlBox": parse_htmlbox_config,
    "Message": parse_message_config,
    "MacroOutput": parse_macrooutput_config,
    "BlockUntilDone": parse_blockuntildone_config,
    "CalgaryInput": parse_calgaryinput_config,
    "CalgaryJoin": parse_calgaryjoin_config,
    "CalgaryCrossCount": parse_calgarycrosscount_config,
    "CalgaryCrossCountAppend": parse_calgarycrosscountappend_config,
    "CalgaryLoader": parse_calgaryloader_config,
    "CASS": parse_cass_config,
    "CASSParse": parse_cassparse_config,
    "ZIP9Coder": parse_zip9coder_config,
    "Geocoder": parse_geocoder_config,
}

# Every catalog tool type resolves to a parser: dedicated semantic parsers above,
# ML-specific parsers for the assisted-modeling/text-mining/computer-vision
# family, and the lossless catalog canonical parser for everything else. This
# is the one-to-one mapping guarantee between Alteryx tool ids and Python.
_ML_TOOL_TYPES = frozenset({
    "AutoML", "Barcode", "BuildFeatures", "Classification", "FeatureTypes", "Fit",
    "ImageProcessing", "ImageProfile", "ImageRecognition", "ImageTemplate",
    "ImageToText", "Insights", "KeyValuePairExtraction", "Modeling",
    "NamedEntityRecognition", "PartOfSpeechTagger", "PDFInput", "PDFToText",
    "Predict", "Regression", "Sentiment", "TextPreProcessing", "TextSummary",
    "TopicModel", "Transformation", "WordCloud", "ZeroShotTextClassification",
})
for _catalog_entry in CATALOG:
    if _catalog_entry.tool_type in TOOL_PARSERS:
        continue
    if _catalog_entry.tool_type in _ML_TOOL_TYPES:
        TOOL_PARSERS[_catalog_entry.tool_type] = make_ml_parser(_catalog_entry.tool_type)
    else:
        TOOL_PARSERS[_catalog_entry.tool_type] = make_catalog_parser(_catalog_entry.tool_type)

# Implementation-specific parsers augment the existing semantic parser so that
# original XML and the installed plugin's normalized settings remain available.
from importlib import import_module as _import_parser_module
from alteryx2python.parser.tool_parsers.common import ToolParserResult as _ToolParserResult


def _merged_local_parser(base, specific):
    def parse(raw):
        first = base(raw) if base else _ToolParserResult({})
        second = specific(raw)
        if isinstance(second, dict):
            second = _ToolParserResult(second)
        return _ToolParserResult(
            normalized_config={**first.normalized_config, **second.normalized_config},
            warnings=[*first.warnings, *second.warnings],
        )
    return parse


for _local_name in ("local_macros", "indb", "predictive", "timeseries", "local_media", "statistics_extra", "ml_extra", "text_models", "local_runtimes", "survival", "local_vision"):
    _local_module = _import_parser_module(f"alteryx2python.tools.{_local_name}")
    for _local_type, _local_parser in _local_module.PARSERS.items():
        TOOL_PARSERS[_local_type] = _merged_local_parser(TOOL_PARSERS.get(_local_type), _local_parser)


def _field_schema(field: ElementTree.Element) -> dict[str, str]:
    return dict(field.attrib)


def _record_info_to_schema(meta_info: ElementTree.Element | None) -> dict[str, object]:
    if meta_info is None:
        return {}
    record_info = meta_info.find("RecordInfo")
    if record_info is None:
        return {"connection": meta_info.attrib.get("connection", "")}
    return {
        "connection": meta_info.attrib.get("connection", ""),
        "fields": [_field_schema(field) for field in record_info.findall("Field")],
    }


def _extract_external_dependencies(node_element: ElementTree.Element) -> list[str]:
    dependencies: list[str] = []
    for file_element in node_element.findall(".//File"):
        text = (file_element.text or "").strip()
        if text:
            dependencies.append(text)
    return dependencies


def _extract_node_anchors(
    node_element: ElementTree.Element,
    incoming_anchor_names: set[str],
    outgoing_anchor_names: set[str],
) -> tuple[list[AnchorIR], list[AnchorIR]]:
    input_anchors = [AnchorIR(name=name, direction="input") for name in sorted(incoming_anchor_names)]
    output_anchors = [AnchorIR(name=name, direction="output") for name in sorted(outgoing_anchor_names)]

    meta_infos = node_element.findall("./Properties/MetaInfo")
    input_names = {anchor.name for anchor in input_anchors}
    output_names = {anchor.name for anchor in output_anchors}
    for meta_info in meta_infos:
        connection_name = meta_info.attrib.get("connection", "").strip()
        if not connection_name:
            continue
        if connection_name in incoming_anchor_names or connection_name in INPUT_ANCHOR_HINTS:
            if connection_name not in input_names:
                input_anchors.append(AnchorIR(name=connection_name, direction="input"))
                input_names.add(connection_name)
        else:
            if connection_name not in output_names:
                output_anchors.append(AnchorIR(name=connection_name, direction="output"))
                output_names.add(connection_name)
    return input_anchors, output_anchors


def _find_root_nodes(root: ElementTree.Element) -> list[ElementTree.Element]:
    return root.findall("./Nodes/Node")


def _build_edges(root: ElementTree.Element) -> list[EdgeIR]:
    edges: list[EdgeIR] = []
    for connection in root.findall("./Connections/Connection"):
        origin = connection.find("Origin")
        destination = connection.find("Destination")
        if origin is None or destination is None:
            continue
        source_node_id = origin.attrib.get("ToolID", "")
        source_anchor = origin.attrib.get("Connection", "")
        target_node_id = destination.attrib.get("ToolID", "")
        target_anchor = destination.attrib.get("Connection", "")
        edge_id = f"{source_node_id}:{source_anchor}->{target_node_id}:{target_anchor}"
        edges.append(
            EdgeIR(
                edge_id=edge_id,
                source_node_id=source_node_id,
                source_anchor=source_anchor,
                target_node_id=target_node_id,
                target_anchor=target_anchor,
                metadata={"raw": _element_to_dict(connection)},
            )
        )
    return edges


def _iter_nodes(node_element: ElementTree.Element, container_id: str | None = None):
    yield node_element, container_id
    child_nodes = node_element.find("ChildNodes")
    if child_nodes is not None:
        parent_tool_id = node_element.attrib.get("ToolID")
        for child_node in child_nodes.findall("Node"):
            yield from _iter_nodes(child_node, container_id=parent_tool_id)


class XmlWorkflowParser(BaseWorkflowParser):
    """Parses Alteryx XML workflows into the canonical IR shell."""

    def parse(self, source_path: Path) -> WorkflowIR:
        contents = source_path.read_bytes()
        return self.parse_xml(contents, source_path)

    def parse_xml(self, contents: str | bytes, source_path: Path) -> WorkflowIR:
        """Parse embedded/configured XML with the original dependency base directory."""
        if isinstance(contents, str):
            contents = contents.encode("utf-8")
        root = ElementTree.fromstring(contents)
        edges = _build_edges(root)

        incoming_anchor_names: dict[str, set[str]] = defaultdict(set)
        outgoing_anchor_names: dict[str, set[str]] = defaultdict(set)
        incoming_edge_ids: dict[str, list[str]] = defaultdict(list)
        outgoing_edge_ids: dict[str, list[str]] = defaultdict(list)
        for edge in edges:
            incoming_anchor_names[edge.target_node_id].add(edge.target_anchor)
            outgoing_anchor_names[edge.source_node_id].add(edge.source_anchor)
            incoming_edge_ids[edge.target_node_id].append(edge.edge_id)
            outgoing_edge_ids[edge.source_node_id].append(edge.edge_id)

        nodes: list[NodeIR] = []
        warnings: list[str] = []
        external_dependencies: set[str] = set()

        for root_node in _find_root_nodes(root):
            for node_element, container_id in _iter_nodes(root_node):
                node_id = node_element.attrib.get("ToolID", "")
                gui_settings = node_element.find("GuiSettings")
                plugin_name = gui_settings.attrib.get("Plugin", "UNKNOWN") if gui_settings is not None else "UNKNOWN"
                tool_type = _normalize_tool_type(plugin_name)
                engine_settings = node_element.find("./Properties/EngineSettings")
                if engine_settings is None:
                    engine_settings = node_element.find("./EngineSettings")
                macro_name = engine_settings.attrib.get("Macro", "") if engine_settings is not None else ""
                macro_tool_type = _normalize_macro_tool_type(macro_name)
                if macro_tool_type is not None:
                    tool_type = macro_tool_type
                    plugin_name = macro_name
                supported_status, warning = _node_supported_status(plugin_name)
                if warning:
                    warnings.append(f"Node {node_id} ({tool_type}): {warning}")

                configuration = node_element.find("./Properties/Configuration")
                raw_config = _element_to_dict(configuration) if configuration is not None else {}
                annotation = node_element.find("./Properties/Annotation")
                annotation_config = _element_to_dict(annotation) if annotation is not None else {}
                if tool_type in INTERFACE_CONFIG_TOOL_TYPES.union({"Action", "Error"}) and annotation_config:
                    raw_config["annotation"] = annotation_config
                config_tool_type = _normalize_config_only_tool_type(raw_config)
                if config_tool_type is not None and tool_type == "UNKNOWN":
                    tool_type = config_tool_type
                if container_id is not None:
                    raw_config["container_id"] = container_id

                child_nodes = node_element.find("ChildNodes")
                if child_nodes is not None:
                    raw_config["child_node_ids"] = [child.attrib.get("ToolID", "") for child in child_nodes.findall("Node")]

                meta_infos = node_element.findall("./Properties/MetaInfo")
                schema_by_connection = {
                    meta_info.attrib.get("connection", ""): _record_info_to_schema(meta_info)
                    for meta_info in meta_infos
                    if meta_info.attrib.get("connection", "")
                }
                if len(schema_by_connection) == 1:
                    expected_output_schema = dict(next(iter(schema_by_connection.values())))
                else:
                    expected_output_schema = schema_by_connection

                metadata: dict[str, object] = {
                    "plugin_name": plugin_name,
                    "raw_gui_settings": _element_to_dict(gui_settings) if gui_settings is not None else {},
                    "meta_info": schema_by_connection,
                }
                catalog_entry = catalog_entry_for_plugin(plugin_name)
                if catalog_entry is not None:
                    metadata["catalog"] = {
                        "tool_type": catalog_entry.tool_type,
                        "display_name": catalog_entry.display_name,
                        "category": catalog_entry.category,
                        "engine_dll": catalog_entry.engine_dll,
                        "engine_entry": catalog_entry.engine_entry,
                        "engine_macro": catalog_entry.engine_macro,
                        "source": catalog_entry.source,
                        "gui_only": catalog_entry.gui_only,
                    }
                if annotation_config:
                    metadata["annotation"] = annotation_config

                input_anchors, output_anchors = _extract_node_anchors(
                    node_element,
                    incoming_anchor_names.get(node_id, set()),
                    outgoing_anchor_names.get(node_id, set()),
                )

                parser = TOOL_PARSERS.get(tool_type)
                if parser is None:
                    normalized_config = raw_config
                else:
                    parsed = parser(raw_config)
                    normalized_config = parsed.normalized_config
                    warnings.extend(
                        [f"Node {node_id} ({tool_type}): {message}" for message in parsed.warnings]
                    )
                if isinstance(normalized_config, dict):
                    normalized_config = {**normalized_config, "base_dir": str(source_path.parent)}
                    if macro_name:
                        normalized_config.update(macro_path=macro_name, macro_tool_type=tool_type)

                for dependency in _extract_external_dependencies(node_element):
                    external_dependencies.add(dependency)

                config = {
                    **raw_config,
                    "raw": raw_config,
                    "normalized": normalized_config,
                }

                nodes.append(
                    NodeIR(
                        node_id=node_id,
                        source_tool_id=node_id,
                        tool_type=tool_type,
                        tool_name=plugin_name,
                        config=config,
                        input_anchors=input_anchors,
                        output_anchors=output_anchors,
                        incoming_edges=list(incoming_edge_ids.get(node_id, [])),
                        outgoing_edges=list(outgoing_edge_ids.get(node_id, [])),
                        expected_input_schema={},
                        expected_output_schema=expected_output_schema,
                        metadata=metadata,
                        supported_status=supported_status,
                    )
                )

        return WorkflowIR(
            workflow_id=root.attrib.get("WorkflowId", source_path.stem),
            workflow_name=root.attrib.get("name", source_path.stem),
            source_file=str(source_path),
            source_hash=sha256(contents).hexdigest(),
            parser_version="0.1.0",
            migration_spec_version="0.1.0",
            nodes=nodes,
            edges=edges,
            external_dependencies=sorted(external_dependencies),
            warnings=warnings,
            classification="CLASS_D_PARTIAL_MIGRATION_ONLY",
            source_xml=ElementTree.tostring(root, encoding="unicode"),
        )

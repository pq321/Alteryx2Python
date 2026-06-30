from __future__ import annotations

from collections import Counter
from typing import Any
from xml.etree import ElementTree

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _local_name(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[1]
    return tag


def _element_text(element: ElementTree.Element) -> str:
    return (element.text or "").strip()


def _outer_xml(element: ElementTree.Element) -> str:
    return ElementTree.tostring(element, encoding="unicode", short_empty_elements=True)


def _descendants_including_root(root: ElementTree.Element) -> list[ElementTree.Element]:
    return [root, *list(root.iter())[1:]]


def _auto_targets(root: ElementTree.Element) -> list[ElementTree.Element]:
    descendants = list(root.iter())[1:]
    if not descendants:
        return []

    names = [_local_name(element.tag) for element in descendants]
    counts = Counter(names)
    repeated_parent_names = {
        name
        for name, count in counts.items()
        if count > 1 and any(len(list(element)) > 0 for element in descendants if _local_name(element.tag) == name)
    }
    if repeated_parent_names:
        first_name = next(name for name in names if name in repeated_parent_names)
        return [element for element in descendants if _local_name(element.tag) == first_name]

    leaf_nodes = [element for element in descendants if len(list(element)) == 0]
    return leaf_nodes or descendants[:1]


def _target_elements(root: ElementTree.Element, config: dict[str, Any]) -> list[ElementTree.Element]:
    if bool(config.get("parse_root", False)):
        return [root]

    xml_element = str(config.get("xml_element", "")).strip()
    if xml_element:
        return [
            element
            for element in _descendants_including_root(root)
            if _local_name(element.tag) == xml_element
        ]

    return _auto_targets(root)


def _append_element_values(
    output_row: dict[str, Any],
    element: ElementTree.Element,
    config: dict[str, Any],
) -> None:
    tag_name = _local_name(element.tag)
    output_row[tag_name] = _element_text(element)
    for attr_name, attr_value in element.attrib.items():
        output_row[_local_name(attr_name)] = attr_value

    if bool(config.get("child_values", False)):
        for child in list(element):
            output_row[_local_name(child.tag)] = _element_text(child)

    if bool(config.get("outer_xml", False)):
        output_row[f"{tag_name}_OuterXML"] = _outer_xml(element)


def _ordered_columns(input_columns: list[str], rows: list[dict[str, Any]]) -> list[str]:
    columns = list(input_columns)
    seen = set(columns)
    for row in rows:
        for column in row:
            if column not in seen:
                columns.append(column)
                seen.add(column)
    return columns


def xmlparse_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("XMLParse tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    xml_field = str(config.get("xml_field", ""))
    if not xml_field:
        raise ValueError("XMLParse tool config requires xml_field")
    ensure_fields_exist(input_frame, [xml_field])

    ignore_errors = bool(config.get("ignore_errors", False))
    rows: list[dict[str, Any]] = []
    for source_row in input_frame.to_dict("records"):
        source_xml = "" if pd.isna(source_row[xml_field]) else str(source_row[xml_field])
        try:
            root = ElementTree.fromstring(source_xml)
        except ElementTree.ParseError as exc:
            if ignore_errors:
                rows.append(dict(source_row))
                continue
            raise ValueError(f"XMLParse failed to parse field {xml_field}") from exc

        for element in _target_elements(root, config):
            output_row = dict(source_row)
            _append_element_values(output_row, element, config)
            rows.append(output_row)

    output = pd.DataFrame(rows, columns=_ordered_columns(list(input_frame.columns), rows))
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="XMLParse",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "xml_field": xml_field,
            "xml_element": config.get("xml_element", ""),
            "child_values": config.get("child_values", False),
            "outer_xml": config.get("outer_xml", False),
            "parse_root": config.get("parse_root", False),
            "ignore_errors": ignore_errors,
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class XMLParseTool(BaseTool):
    tool_type = "XMLParse"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return xmlparse_tool(inputs, config, context)

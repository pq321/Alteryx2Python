from __future__ import annotations

from typing import TYPE_CHECKING

from alteryx2python.tools.registry import TOOL_REGISTRY

if TYPE_CHECKING:
    from alteryx2python.ir.models import NodeIR
    from alteryx2python.ir.models import WorkflowIR


def _normalized_config(node: "NodeIR") -> dict[str, object]:
    normalized = node.config.get("normalized", node.config)
    return normalized if isinstance(normalized, dict) else {}


def certification_issues_for_nodes(workflow: "WorkflowIR", node_ids: list[str]) -> list[str]:
    nodes_by_id = {node.node_id: node for node in workflow.nodes}
    issues: list[str] = []

    for node_id in node_ids:
        node = nodes_by_id.get(node_id)
        if node is None:
            issues.append(f"Certification path references unknown node {node_id}")
            continue
        try:
            metadata = TOOL_REGISTRY.get(node.tool_type)
        except KeyError:
            issues.append(f"Node {node_id} uses unsupported tool {node.tool_type}")
            continue
        if not metadata.supports_certification:
            issues.append(f"Node {node_id} tool {node.tool_type} is not marked certifiable")
            continue
        issues.extend(
            f"Node {node_id} {issue}"
            for issue in _config_certification_issues(node.tool_type, _normalized_config(node))
        )

    return issues


def assert_nodes_certifiable(workflow: "WorkflowIR", node_ids: list[str]) -> None:
    issues = certification_issues_for_nodes(workflow, node_ids)
    if issues:
        raise AssertionError("Certification precheck failed: " + "; ".join(issues))


def _config_certification_issues(tool_type: str, config: dict[str, object]) -> list[str]:
    if tool_type == "DbFileInput":
        return _dbfileinput_issues(config)
    if tool_type == "DbFileOutput":
        return _dbfileoutput_issues(config)
    if tool_type == "Join":
        return _join_issues(config)
    if tool_type == "Select":
        return _select_issues(config)
    if tool_type == "Sort":
        return _sort_issues(config)
    if tool_type == "TextInput":
        return _textinput_issues(config)
    return []


def _file_format(config: dict[str, object]) -> str:
    attrs = config.get("file_attributes")
    if not isinstance(attrs, dict):
        return ""
    value = attrs.get("FileFormat", "")
    return str(value) if value is not None else ""


def _dbfileinput_issues(config: dict[str, object]) -> list[str]:
    file_format = _file_format(config)
    file_value = str(config.get("file", ""))
    if file_format == "19" or file_value.lower().split("|||", 1)[0].endswith(".yxdb"):
        return ["DbFileInput config is not certifiable: YXDB input is deferred"]
    if file_format not in {"", "0", "25"}:
        return [f"DbFileInput config is not certifiable: FileFormat {file_format} is not observed"]
    if "|||" in file_value:
        selector = file_value.split("|||", 1)[1].strip().strip("`")
        if selector == "<List of Sheet Names>" or (selector and not selector.endswith("$")):
            return ["DbFileInput config is not certifiable: only sheet selectors are observed for Excel"]
    return []


def _dbfileoutput_issues(config: dict[str, object]) -> list[str]:
    file_format = _file_format(config)
    file_value = str(config.get("file", ""))
    if file_format == "25" or file_value.lower().split("|||", 1)[0].endswith((".xlsx", ".xls")):
        return ["DbFileOutput config is not certifiable: Excel output is deferred"]
    if file_format not in {"", "0"}:
        return [f"DbFileOutput config is not certifiable: FileFormat {file_format} is not observed"]
    return []


def _join_issues(config: dict[str, object]) -> list[str]:
    if config.get("join_by_record_pos") is True:
        return ["Join config is not certifiable: join-by-record-position is deferred"]
    joins = config.get("joins")
    if not isinstance(joins, list) or len(joins) != 2:
        return ["Join config is not certifiable: expected observed Left/Right field join"]
    return []


def _select_issues(config: dict[str, object]) -> list[str]:
    select_fields = config.get("select_fields")
    if not isinstance(select_fields, list) or not select_fields:
        return ["Select config is not certifiable: no observed select_fields"]
    for field in select_fields:
        if not isinstance(field, dict):
            return ["Select config is not certifiable: malformed select field"]
        source = str(field.get("source", ""))
        if not source:
            return ["Select config is not certifiable: select field requires source"]
    return []


def _sort_issues(config: dict[str, object]) -> list[str]:
    sort_fields = config.get("sort_fields")
    if not isinstance(sort_fields, list) or not sort_fields:
        return ["Sort config is not certifiable: no observed sort_fields"]
    for field in sort_fields:
        if not isinstance(field, dict):
            return ["Sort config is not certifiable: malformed sort field"]
        if not str(field.get("field", "")):
            return ["Sort config is not certifiable: sort field requires field"]
        order = str(field.get("order", "Ascending")).lower()
        if order not in {"ascending", "descending"}:
            return [f"Sort config is not certifiable: order {field.get('order')} is not observed"]
    return []


def _textinput_issues(config: dict[str, object]) -> list[str]:
    fields = config.get("fields")
    rows = config.get("rows")
    if not isinstance(fields, list) or not isinstance(rows, list):
        return ["TextInput config is not certifiable: expected observed fields and rows"]
    if not fields:
        return ["TextInput config is not certifiable: fields are required"]
    expected_num_rows = config.get("num_rows")
    if expected_num_rows is not None and expected_num_rows != len(rows):
        return ["TextInput config is not certifiable: num_rows does not match rows"]
    for row in rows:
        if not isinstance(row, list):
            return ["TextInput config is not certifiable: row entries must be lists"]
        if len(row) != len(fields):
            return ["TextInput config is not certifiable: row width does not match fields"]
    return []

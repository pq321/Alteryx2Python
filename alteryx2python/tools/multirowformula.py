from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import ensure_fields_exist, snapshot_schema
from alteryx2python.expressions.evaluator import evaluate_expression
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _target_field(config: dict[str, Any]) -> str:
    if bool(config.get("update_field", False)):
        return str(config.get("update_field_name", ""))
    return str(config.get("create_field_name", ""))


def _empty_value_for(field_name: str, target_field: str, field_type: str) -> Any:
    if field_name == target_field and field_type.lower() in {"bool", "byte", "int16", "int32", "int64", "fixeddecimal", "double", "float"}:
        return 0
    return None


def _coerce_value(value: Any, field_type: str) -> Any:
    if value is None or pd.isna(value):
        return value
    normalized = field_type.lower()
    if normalized == "bool":
        return bool(value)
    if normalized in {"byte", "int16", "int32", "int64"}:
        return int(value)
    if normalized in {"fixeddecimal", "double", "float"}:
        return float(value)
    return value


def _group_key(row: dict[str, Any], group_by_fields: list[str]) -> tuple[Any, ...]:
    return tuple(row.get(field) for field in group_by_fields)


def _resolve_reference_index(position: int, offset: int, group_positions: list[int], other_rows: str) -> int | None:
    group_index = group_positions.index(position)
    target_group_index = group_index + offset
    if 0 <= target_group_index < len(group_positions):
        return group_positions[target_group_index]
    if other_rows.lower() == "nearest" and group_positions:
        return group_positions[0] if target_group_index < 0 else group_positions[-1]
    return None


def _add_row_references(
    row_context: dict[str, Any],
    rows: list[dict[str, Any]],
    position: int,
    group_positions: list[int],
    config: dict[str, Any],
) -> None:
    num_rows = int(config.get("num_rows", 1))
    other_rows = str(config.get("other_rows", "Empty"))
    target_field = _target_field(config)
    field_type = str(config.get("create_field_type", ""))
    field_names = set().union(*(row.keys() for row in rows)) if rows else set()
    for offset in range(-num_rows, num_rows + 1):
        if offset == 0:
            continue
        reference_index = _resolve_reference_index(position, offset, group_positions, other_rows)
        for field_name in field_names:
            key = f"Row{offset}:{field_name}"
            if reference_index is None:
                row_context[key] = _empty_value_for(field_name, target_field, field_type)
            else:
                row_context[key] = rows[reference_index].get(field_name)


def multirowformula_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    if "Input" not in inputs:
        raise KeyError("MultiRowFormula tool requires an Input anchor")
    input_frame = inputs["Input"]
    if not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    target_field = _target_field(config)
    if not target_field:
        raise ValueError("MultiRowFormula config requires a target field")
    expression = str(config.get("expression", ""))
    if not expression:
        raise ValueError("MultiRowFormula config requires expression")
    group_by_fields = [str(field) for field in config.get("group_by_fields", [])]
    ensure_fields_exist(input_frame, group_by_fields)

    rows = input_frame.copy().to_dict("records")
    if not bool(config.get("update_field", False)):
        for row in rows:
            row[target_field] = _empty_value_for(target_field, target_field, str(config.get("create_field_type", "")))

    positions_by_group: dict[tuple[Any, ...], list[int]] = {}
    for index, row in enumerate(rows):
        positions_by_group.setdefault(_group_key(row, group_by_fields), []).append(index)

    parsed_expression = parse_expression(expression)
    for index, row in enumerate(rows):
        row_context = dict(row)
        _add_row_references(
            row_context,
            rows,
            index,
            positions_by_group[_group_key(row, group_by_fields)],
            config,
        )
        row[target_field] = _coerce_value(
            evaluate_expression(parsed_expression, row_context),
            str(config.get("create_field_type", "")),
        )

    output = pd.DataFrame(rows)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="MultiRowFormula",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame},
        outputs=outputs,
        status="success",
        config={
            "target_field": target_field,
            "expression": expression,
            "group_by_fields": group_by_fields,
            "other_rows": config.get("other_rows", "Empty"),
            "num_rows": config.get("num_rows", 1),
            "input_schema": snapshot_schema(input_frame),
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class MultiRowFormulaTool(BaseTool):
    tool_type = "MultiRowFormula"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return multirowformula_tool(inputs, config, context)

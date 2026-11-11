from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import SchemaSnapshot, snapshot_schema


@dataclass(slots=True, frozen=True)
class ContractAssertion:
    assertion_type: str
    target: str
    expected: Any
    actual: Any
    passed: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.assertion_type,
            "target": self.target,
            "expected": self.expected,
            "actual": self.actual,
            "passed": self.passed,
            "message": self.message,
        }


@dataclass(slots=True, frozen=True)
class ContractEvidence:
    node_id: str
    tool_type: str
    input_schemas: dict[str, SchemaSnapshot]
    output_schemas: dict[str, SchemaSnapshot]
    assertions: list[ContractAssertion] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(assertion.passed for assertion in self.assertions)

    def failures(self) -> list[ContractAssertion]:
        return [assertion for assertion in self.assertions if not assertion.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "tool_type": self.tool_type,
            "passed": self.passed,
            "input_schemas": self.input_schemas,
            "output_schemas": self.output_schemas,
            "assertions": [assertion.to_dict() for assertion in self.assertions],
        }


def validate_node_contract(
    *,
    node_id: str,
    tool_type: str,
    declared_output_anchors: tuple[str, ...],
    inputs: dict[str, pd.DataFrame],
    outputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    expected_output_schema: dict[str, Any] | None = None,
) -> ContractEvidence:
    assertions: list[ContractAssertion] = []
    assertions.extend(_assert_declared_output_anchors(declared_output_anchors, outputs))
    assertions.extend(_assert_outputs_are_dataframes(outputs))
    if config.get("enforce_expected_output_schema") is True:
        assertions.extend(_assert_expected_output_schema(expected_output_schema or {}, outputs))
    assertions.extend(_assert_inferred_tool_contract(tool_type, inputs, outputs, config))

    evidence = ContractEvidence(
        node_id=node_id,
        tool_type=tool_type,
        input_schemas={
            anchor: snapshot_schema(frame)
            for anchor, frame in inputs.items()
            if isinstance(frame, pd.DataFrame)
        },
        output_schemas={
            anchor: snapshot_schema(frame)
            for anchor, frame in outputs.items()
            if isinstance(frame, pd.DataFrame)
        },
        assertions=assertions,
    )
    failures = evidence.failures()
    if failures:
        messages = "; ".join(failure.message for failure in failures)
        raise AssertionError(f"Contract validation failed for node {node_id} ({tool_type}): {messages}")
    return evidence


def _assert_declared_output_anchors(
    declared_output_anchors: tuple[str, ...],
    outputs: dict[str, pd.DataFrame],
) -> list[ContractAssertion]:
    assertions: list[ContractAssertion] = []
    for anchor in declared_output_anchors:
        assertions.append(
            _assertion(
                "anchor_emitted",
                target=anchor,
                expected=True,
                actual=anchor in outputs,
                message=f"Output anchor {anchor!r} must be emitted",
            )
        )
    undeclared = sorted(set(outputs) - set(declared_output_anchors))
    if undeclared and declared_output_anchors:
        assertions.append(
            _assertion(
                "no_undeclared_output_anchors",
                target="outputs",
                expected=[],
                actual=undeclared,
                message=f"Undeclared output anchors emitted: {', '.join(undeclared)}",
            )
        )
    return assertions


def _assert_outputs_are_dataframes(outputs: dict[str, pd.DataFrame]) -> list[ContractAssertion]:
    return [
        _assertion(
            "output_is_dataframe",
            target=anchor,
            expected="pandas.DataFrame",
            actual=type(frame).__name__,
            message=f"Output anchor {anchor!r} must contain a pandas DataFrame",
            passed=isinstance(frame, pd.DataFrame),
        )
        for anchor, frame in outputs.items()
    ]


def _assert_expected_output_schema(
    expected_output_schema: dict[str, Any],
    outputs: dict[str, pd.DataFrame],
) -> list[ContractAssertion]:
    if not expected_output_schema:
        return []
    assertions: list[ContractAssertion] = []
    if "fields" in expected_output_schema:
        assertions.extend(_assert_schema_fields("Output", expected_output_schema, outputs))
        return assertions
    for anchor, schema in expected_output_schema.items():
        if isinstance(schema, dict) and "fields" in schema:
            assertions.extend(_assert_schema_fields(str(anchor), schema, outputs))
    return assertions


def _assert_schema_fields(
    anchor: str,
    expected_schema: dict[str, Any],
    outputs: dict[str, pd.DataFrame],
) -> list[ContractAssertion]:
    expected_columns = [
        str(field["name"])
        for field in expected_schema.get("fields", [])
        if isinstance(field, dict) and "name" in field
    ]
    if anchor not in outputs:
        return [
            _assertion(
                "expected_schema_anchor_emitted",
                target=anchor,
                expected=True,
                actual=False,
                message=f"Expected schema anchor {anchor!r} must be emitted",
            )
        ]
    return [
        _assertion(
            "column_order_equals",
            target=anchor,
            expected=expected_columns,
            actual=list(outputs[anchor].columns),
            message=f"Output anchor {anchor!r} columns must match expected schema",
        )
    ]


def _assert_inferred_tool_contract(
    tool_type: str,
    inputs: dict[str, pd.DataFrame],
    outputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> list[ContractAssertion]:
    if tool_type == "Select":
        return _assert_select_contract(inputs, outputs, config)
    if tool_type == "Formula":
        return _assert_formula_contract(inputs, outputs, config)
    if tool_type == "Filter":
        return _assert_filter_contract(inputs, outputs)
    if tool_type == "Union":
        return _assert_union_contract(inputs, outputs, config)
    if tool_type == "Join":
        return _assert_join_contract(inputs, outputs)
    return []


def _assert_select_contract(
    inputs: dict[str, pd.DataFrame],
    outputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> list[ContractAssertion]:
    if "Input" not in inputs or "Output" not in outputs:
        return []
    input_frame = inputs["Input"]
    output = outputs["Output"]
    expected_columns = _select_expected_columns(input_frame, config)
    return [
        _assertion(
            "column_order_equals",
            target="Output",
            expected=expected_columns,
            actual=list(output.columns),
            message="Select output columns must match selected, renamed, and unknown fields",
        ),
        _assertion(
            "row_count_equals_input",
            target="Output",
            expected=len(input_frame.index),
            actual=len(output.index),
            message="Select must preserve row count",
        ),
    ]


def _select_expected_columns(input_frame: pd.DataFrame, config: dict[str, Any]) -> list[str]:
    fields = [field for field in config.get("select_fields", []) if isinstance(field, dict)]
    explicit_sources = {str(field.get("source")) for field in fields if field.get("source") != "*Unknown"}
    columns: list[str] = []
    for field in fields:
        if field.get("selected", True) is False:
            continue
        source = str(field.get("source", ""))
        if source == "*Unknown":
            columns.extend(column for column in input_frame.columns if column not in explicit_sources)
        elif source:
            columns.append(str(field.get("rename", source)))
    expected_output_columns = _expected_output_columns(config.get("expected_output_schema"))
    if expected_output_columns:
        ordered = [column for column in expected_output_columns if column in columns]
        extras = [column for column in columns if column not in ordered]
        return [*ordered, *extras]
    return columns


def _assert_formula_contract(
    inputs: dict[str, pd.DataFrame],
    outputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> list[ContractAssertion]:
    if "Input" not in inputs or "Output" not in outputs:
        return []
    input_frame = inputs["Input"]
    output = outputs["Output"]
    formula_fields = [
        str(field["field"])
        for field in config.get("formula_fields", [])
        if isinstance(field, dict) and field.get("enabled", True) is not False and field.get("field")
    ]
    expected_columns = list(input_frame.columns)
    for field in formula_fields:
        if field not in expected_columns:
            expected_columns.append(field)
    return [
        _assertion(
            "column_order_equals",
            target="Output",
            expected=expected_columns,
            actual=list(output.columns),
            message="Formula output columns must preserve input columns and append new formula fields",
        ),
        _assertion(
            "row_count_equals_input",
            target="Output",
            expected=len(input_frame.index),
            actual=len(output.index),
            message="Formula must preserve row count",
        ),
    ]


def _assert_filter_contract(
    inputs: dict[str, pd.DataFrame],
    outputs: dict[str, pd.DataFrame],
) -> list[ContractAssertion]:
    if "Input" not in inputs:
        return []
    input_frame = inputs["Input"]
    assertions: list[ContractAssertion] = []
    for anchor in ("True", "False"):
        if anchor in outputs:
            assertions.append(
                _assertion(
                    "column_order_equals",
                    target=anchor,
                    expected=list(input_frame.columns),
                    actual=list(outputs[anchor].columns),
                    message=f"Filter {anchor} output columns must preserve input schema",
                )
            )
    if "True" in outputs and "False" in outputs:
        assertions.append(
            _assertion(
                "row_count_equals_sum_of_anchors",
                target="True+False",
                expected=len(input_frame.index),
                actual=len(outputs["True"].index) + len(outputs["False"].index),
                message="Filter True and False row counts must partition the input rows",
            )
        )
    return assertions


def _assert_union_contract(
    inputs: dict[str, pd.DataFrame],
    outputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> list[ContractAssertion]:
    if not inputs or "Output" not in outputs:
        return []
    from alteryx2python.tools.union import _ordered_input_anchors
    ordered_frames = [inputs[anchor] for anchor in _ordered_input_anchors(inputs, config)]
    mode = str(config.get("mode", "ByName")).lower()
    if mode == "bypos":
        expected_columns = _expected_output_columns(config.get("expected_output_schema")) or list(ordered_frames[0].columns)
        message = "Union ByPos output columns must match the first input columns"
    else:
        expected_columns = list(dict.fromkeys(column for frame in ordered_frames for column in frame.columns))
        message = "Union output columns must be the by-name union of input columns"
    expected_row_count = sum(len(frame.index) for frame in ordered_frames)
    output = outputs["Output"]
    return [
        _assertion(
            "column_order_equals",
            target="Output",
            expected=expected_columns,
            actual=list(output.columns),
            message=message,
        ),
        _assertion(
            "row_count_equals_sum_of_inputs",
            target="Output",
            expected=expected_row_count,
            actual=len(output.index),
            message="Union output row count must equal the sum of input row counts",
        ),
    ]


def _assert_join_contract(
    inputs: dict[str, pd.DataFrame],
    outputs: dict[str, pd.DataFrame],
) -> list[ContractAssertion]:
    assertions = [
        _assertion(
            "anchor_emitted",
            target=anchor,
            expected=True,
            actual=anchor in outputs,
            message=f"Join must emit {anchor!r} anchor",
        )
        for anchor in ("Join", "Left", "Right")
    ]
    for anchor in ("Left", "Right"):
        if anchor in inputs and anchor in outputs:
            assertions.append(
                _assertion(
                    "row_count_less_than_or_equal_input",
                    target=anchor,
                    expected=True,
                    actual=len(outputs[anchor].index) <= len(inputs[anchor].index),
                    message=f"Join {anchor} unjoined output row count must not exceed {anchor} input row count",
                )
            )
    return assertions


def _expected_output_columns(schema: Any) -> list[str]:
    if not isinstance(schema, dict):
        return []
    if "fields" in schema:
        return _field_names(schema.get("fields"))
    output_schema = schema.get("Output")
    if isinstance(output_schema, dict):
        return _field_names(output_schema.get("fields"))
    return []


def _field_names(fields: Any) -> list[str]:
    if not isinstance(fields, list):
        return []
    return [str(field["name"]) for field in fields if isinstance(field, dict) and "name" in field]


def _assertion(
    assertion_type: str,
    *,
    target: str,
    expected: Any,
    actual: Any,
    message: str,
    passed: bool | None = None,
) -> ContractAssertion:
    assertion_passed = expected == actual if passed is None else passed
    return ContractAssertion(
        assertion_type=assertion_type,
        target=target,
        expected=expected,
        actual=actual,
        passed=assertion_passed,
        message=message,
    )

from __future__ import annotations

from typing import Any

from alteryx2python.expressions.ast import FieldReference, LiteralExpression
from alteryx2python.expressions.errors import UnsupportedExpressionError


def evaluate_expression(node, row: dict[str, Any]) -> Any:
    if isinstance(node, LiteralExpression):
        return node.value
    if isinstance(node, FieldReference):
        return row[node.name]
    raise UnsupportedExpressionError("Expression evaluator does not support this node yet")
from __future__ import annotations

from alteryx2python.expressions.ast import FieldReference, LiteralExpression
from alteryx2python.expressions.errors import UnsupportedExpressionError


def parse_expression(expression: str):
    stripped = expression.strip()
    if not stripped:
        raise UnsupportedExpressionError("Empty expressions are not supported")
    if stripped.startswith("[") and stripped.endswith("]"):
        return FieldReference(stripped[1:-1])
    if stripped.isdigit():
        return LiteralExpression(int(stripped))
    raise UnsupportedExpressionError(
        "Expression parsing is not implemented beyond trivial literals and field references"
    )
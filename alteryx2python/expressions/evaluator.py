from __future__ import annotations

from typing import Any

from alteryx2python.expressions.ast import (
    BinaryExpression,
    ConditionalExpression,
    FieldReference,
    FunctionExpression,
    LiteralExpression,
    UnaryExpression,
)
from alteryx2python.expressions.errors import UnsupportedExpressionError
from alteryx2python.expressions.functions import call_function


def evaluate_expression(node, row: dict[str, Any]) -> Any:
    if isinstance(node, LiteralExpression):
        return node.value
    if isinstance(node, FieldReference):
        return row[node.name]
    if isinstance(node, ConditionalExpression):
        branch = node.true_value if bool(evaluate_expression(node.condition, row)) else node.false_value
        return evaluate_expression(branch, row)
    if isinstance(node, UnaryExpression):
        value = evaluate_expression(node.operand, row)
        if node.operator == "!":
            return not bool(value)
        raise UnsupportedExpressionError(f"Unsupported unary operator: {node.operator}")
    if isinstance(node, BinaryExpression):
        return _evaluate_binary(node, row)
    if isinstance(node, FunctionExpression):
        return call_function(node.name, [evaluate_expression(arg, row) for arg in node.args])
    raise UnsupportedExpressionError("Expression evaluator does not support this node yet")


def _evaluate_binary(node: BinaryExpression, row: dict[str, Any]) -> Any:
    if node.operator == "AND":
        return bool(evaluate_expression(node.left, row)) and bool(evaluate_expression(node.right, row))
    if node.operator == "OR":
        return bool(evaluate_expression(node.left, row)) or bool(evaluate_expression(node.right, row))

    left = evaluate_expression(node.left, row)
    right = evaluate_expression(node.right, row)
    if node.operator == "+":
        return left + right
    if node.operator == "-":
        return left - right
    if node.operator == "*":
        return left * right
    if node.operator == "/":
        return left / right
    if node.operator == ">":
        return left > right
    if node.operator == ">=":
        return left >= right
    if node.operator == "<":
        return left < right
    if node.operator == "<=":
        return left <= right
    if node.operator == "==":
        return left == right
    if node.operator == "!=":
        return left != right
    raise UnsupportedExpressionError(f"Unsupported binary operator: {node.operator}")

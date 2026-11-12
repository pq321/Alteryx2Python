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


def evaluate_expression(node, row: dict[str, Any], constants: dict[str, Any] | None = None) -> Any:
    if isinstance(node, LiteralExpression):
        return node.value
    if isinstance(node, FieldReference):
        if constants is None:
            from alteryx2python.runtime.variables import ACTIVE_VARIABLES
            constants = ACTIVE_VARIABLES.get()
        try:
            return row[node.name]
        except KeyError:
            # Engine constants ([Engine.WorkflowDirectory] and friends) are
            # valid field references outside the record context.
            if constants:
                name = node.name.strip('%')
                if name in constants:
                    return constants[name]
                bare = node.name.removeprefix("Engine.")
                if bare in constants:
                    return constants[bare]
            raise
    if isinstance(node, ConditionalExpression):
        branch = node.true_value if bool(evaluate_expression(node.condition, row, constants)) else node.false_value
        return evaluate_expression(branch, row, constants)
    if isinstance(node, UnaryExpression):
        value = evaluate_expression(node.operand, row, constants)
        if node.operator == "!":
            return not bool(value)
        raise UnsupportedExpressionError(f"Unsupported unary operator: {node.operator}")
    if isinstance(node, BinaryExpression):
        return _evaluate_binary(node, row, constants)
    if isinstance(node, FunctionExpression):
        return call_function(node.name, [evaluate_expression(arg, row, constants) for arg in node.args])
    raise UnsupportedExpressionError("Expression evaluator does not support this node yet")


def _evaluate_binary(node: BinaryExpression, row: dict[str, Any], constants: dict[str, Any] | None = None) -> Any:
    if node.operator == "AND":
        return bool(evaluate_expression(node.left, row, constants)) and bool(evaluate_expression(node.right, row, constants))
    if node.operator == "OR":
        return bool(evaluate_expression(node.left, row, constants)) or bool(evaluate_expression(node.right, row, constants))

    left = evaluate_expression(node.left, row, constants)
    right = evaluate_expression(node.right, row, constants)
    if node.operator == "+":
        if left is None and isinstance(right, (int, float)):
            left = 0
        if right is None and isinstance(left, (int, float)):
            right = 0
        return left + right
    if node.operator == "-":
        return left - right
    if node.operator == "*":
        return left * right
    if node.operator == "/":
        return left / right
    if node.operator == ">":
        if left is None or right is None:
            return False
        return left > right
    if node.operator == ">=":
        if left is None or right is None:
            return False
        return left >= right
    if node.operator == "<":
        if left is None or right is None:
            return False
        return left < right
    if node.operator == "<=":
        if left is None or right is None:
            return False
        return left <= right
    if node.operator in {"=", "=="}:
        return left == right
    if node.operator == "!=":
        return left != right
    raise UnsupportedExpressionError(f"Unsupported binary operator: {node.operator}")

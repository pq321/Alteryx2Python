from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True, frozen=True)
class ExpressionNode:
    pass


@dataclass(slots=True, frozen=True)
class LiteralExpression(ExpressionNode):
    value: Any


@dataclass(slots=True, frozen=True)
class FieldReference(ExpressionNode):
    name: str


@dataclass(slots=True, frozen=True)
class BinaryExpression(ExpressionNode):
    left: ExpressionNode
    operator: str
    right: ExpressionNode


@dataclass(slots=True, frozen=True)
class UnaryExpression(ExpressionNode):
    operator: str
    operand: ExpressionNode


@dataclass(slots=True, frozen=True)
class FunctionExpression(ExpressionNode):
    name: str
    args: list[ExpressionNode]


@dataclass(slots=True, frozen=True)
class ConditionalExpression(ExpressionNode):
    condition: ExpressionNode
    true_value: ExpressionNode
    false_value: ExpressionNode

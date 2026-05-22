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
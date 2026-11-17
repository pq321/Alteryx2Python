"""Numeric coercion shared by the expression evaluator and generated Python."""

from decimal import Decimal


def as_formula_value(value):
    # Alteryx evaluates FixedDecimal arithmetic as Double before storing the result.
    return float(value) if isinstance(value, Decimal) else value


def arithmetic_operand(value):
    return float('nan') if value is None else as_formula_value(value)


def add_nullable(left, right):
    left, right = as_formula_value(left), as_formula_value(right)
    if left is None and isinstance(right, (int, float)):
        left = 0
    if right is None and isinstance(left, (int, float)):
        right = 0
    return left + right

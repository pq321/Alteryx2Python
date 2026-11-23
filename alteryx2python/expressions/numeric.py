"""Numeric coercion shared by the expression evaluator and generated Python."""

from decimal import Decimal


def as_formula_value(value):
    # Alteryx evaluates FixedDecimal arithmetic as Double before storing the result.
    return float(value) if isinstance(value, Decimal) else value


def as_formula_series(series):
    """Apply FixedDecimal promotion when a column is stored as Python objects."""
    if series.dtype != object:
        return series
    decimal_cells = series.map(lambda value: isinstance(value, Decimal))
    if not decimal_cells.any():
        return series
    result = series.copy()
    result.loc[decimal_cells] = series.loc[decimal_cells].map(as_formula_value)
    return result


def arithmetic_operand(value):
    return float('nan') if value is None else as_formula_value(value)


def add_nullable(left, right):
    left, right = as_formula_value(left), as_formula_value(right)
    if left is None and isinstance(right, str):
        return right
    if right is None and isinstance(left, str):
        return left
    if left is None and isinstance(right, (int, float)):
        left = 0
    if right is None and isinstance(left, (int, float)):
        right = 0
    return left + right

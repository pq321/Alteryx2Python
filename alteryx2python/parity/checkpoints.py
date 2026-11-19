"""Presentation rules for comparing captured data without modifying records."""

from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re

from alteryx2python.expressions.lexer import tokenize


_TEXT_TYPES = {"String", "WString", "V_String", "V_WString"}
_NUMERIC_KINDS = {"int", "float", "decimal"}
_NUMBER_TEXT = re.compile(r"[+-]?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?")
_IDENTIFIER_TEXT = re.compile(r" *(?:0|[1-9][0-9]*)")
_IDENTIFIER_WORDS = {"id", "identifier", "code", "version"}
_DATE_VALUE = re.compile(r"(\d{4}-\d{2}-\d{2})(?:[T ]00:00:00(?:\.0+)?)?")
_ROW_FIELD = re.compile(r"^Row[+-]\d+:", re.IGNORECASE)


def anchor_stem(tool_id, number, direction="outputs"):
    qualifier = "-input" if direction == "inputs" else ""
    return f"node{tool_id}{qualifier}-anchor{number}"


def checkpoint_policy(workflow):
    """Derive grouping keys and protect fields used in null-sensitive operations."""
    protected = set()
    aliases = []
    group_keys = {}
    for node in workflow.nodes:
        config = node.config.get("normalized", {})
        for key in ("unique_fields", "group_by_fields", "group_fields"):
            protected.update(config.get(key, ()))
        for join in config.get("joins", ()):
            protected.update(join.get("fields") or [join.get("field", "")])
        summary = config.get("summarize_fields", ())
        groups = [field for field in summary if field.get("action") == "GroupBy"]
        if groups:
            names = tuple(field.get("rename") or field["field"] for field in groups)
            group_keys[node.node_id] = names
            protected.update(field["field"] for field in groups)
            protected.update(names)
        protected.update(field["field"] for field in summary if "NonNull" in field.get("action", ""))
        for field in config.get("select_fields", ()):
            if field.get("selected") and field.get("source") and field.get("rename"):
                source = field["source"]
                prefix = field.get("input", "")
                aliases.append(({source, source.removeprefix(prefix)}, field["rename"]))
        formulas = config.get("formula_fields", ())
        expressions = [(config.get("field"), config.get("expression"))]
        expressions.extend((field.get("field"), field.get("expression")) for field in formulas if field.get("enabled", True))
        for target, expression in expressions:
            if not expression:
                continue
            tokens = tokenize(expression)
            refs = {_ROW_FIELD.sub("", token[1:-1]) for token in tokens if token.startswith("[") and token.endswith("]")}
            if target:
                aliases.append((refs, target))
            if any(token.casefold() in {"isnull", "isnotnull"} for token in tokens):
                protected.update(refs)
    protected = {field.casefold() for field in protected}
    while True:
        upstream = {field.casefold() for sources, target in aliases if target.casefold() in protected for field in sources}
        if upstream <= protected:
            break
        protected.update(upstream)
    return protected, group_keys


def _column_kind(rows, index):
    kind = None
    for row in rows:
        if index >= len(row) or row[index]["kind"] == "null":
            continue
        current = row[index]["kind"]
        if current in {"decimal", "float"}:
            current = "number"
        if kind is None or (kind == "int" and current == "number"):
            kind = current
        elif kind != current and (kind, current) != ("number", "int"):
            return None
    return kind


def _identifier_name(name):
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return bool(_IDENTIFIER_WORDS.intersection(re.findall(r"[a-z]+", words.casefold())))


def _distinct_identifier_padding(rows, index):
    originals = {}
    for row in rows:
        if index >= len(row) or row[index]["kind"] != "string":
            continue
        value = row[index]["value"]
        if _IDENTIFIER_TEXT.fullmatch(value):
            if originals.setdefault(value.lstrip(" "), value) != value:
                return False
    return True


def _numeric_text_rules(expected, actual, rules, protected):
    # Compare only cross-type columns. Numeric-looking text on both sides is still text.
    counts = [Counter(snapshot["columns"]) for snapshot in (expected, actual)]
    indexes = {name: index for index, name in enumerate(actual["columns"])}
    left_rows, right_rows = rows = expected["rows"], actual["rows"]
    for left, name in enumerate(expected["columns"]):
        if any(count[name] != 1 for count in counts) or rules.get(name) == "date":
            continue
        right = indexes[name]
        kinds = (_column_kind(left_rows, left), _column_kind(right_rows, right))
        if "string" not in kinds or not {"int", "number"}.intersection(kinds):
            continue
        # A protected integer may be an identifier. A protected float or decimal can
        # represent a numeric join key while still requiring distinct nulls and blanks.
        identifier = _identifier_name(name) or ("int" in kinds and name.casefold() in protected)
        if identifier:
            text_side = kinds.index("string")
            if "int" not in kinds or not _distinct_identifier_padding(rows[text_side], (left, right)[text_side]):
                continue
        rules[name] = ("identifier_text" if identifier else "numeric_text", rules.get(name))


def coarse_rules(snapshot, actual, protected):
    fields = Counter(snapshot["columns"])
    rules = {}
    for field in snapshot.get("schema") or ():
        name, dtype = field["name"], field.get("type")
        if fields[name] != 1:
            continue
        if dtype == "Date":
            rules[name] = "date"
        elif dtype == "FixedDecimal":
            scale = str(field.get("scale"))
            if scale.isdecimal() and int(scale) < 50:
                rules[name] = int(scale)
        elif dtype in _TEXT_TYPES and name.casefold() not in protected and not _identifier_name(name):
            rules[name] = "empty"
    _numeric_text_rules(snapshot, actual, rules, protected)
    return rules


def _text_number(cell, mode, fallback):
    kind, value = cell["kind"], cell.get("value")
    if mode == "identifier_text":
        if kind in {"int", "string"} and _IDENTIFIER_TEXT.fullmatch(value):
            return {"kind": "coarse_identifier", "value": value.lstrip(" ")}
    elif kind in _NUMERIC_KINDS or (kind == "string" and _NUMBER_TEXT.fullmatch(value)):
        try:
            number = Decimal(str(float.fromhex(value))) if kind == "float" else Decimal(value)
        except (InvalidOperation, OverflowError, ValueError):
            return cell
        if number.is_finite():
            if isinstance(fallback, int):
                return _scaled_number(cell, number, fallback)
            if number.is_zero():
                return {"kind": "coarse_number", "value": "0"}
            # Trim trailing zeros without Decimal's context-dependent rounding.
            sign, digits, exponent = number.as_tuple()
            coefficient = "".join(map(str, digits))
            significant = coefficient.rstrip("0")
            exponent += len(coefficient) - len(significant)
            return {"kind": "coarse_number", "value": f"{'-' if sign else ''}{significant}e{exponent}"}
    return coarse_cell(cell, fallback)


def _scaled_number(cell, number, scale):
    if number.is_finite():
        try:
            with localcontext() as context:
                context.prec = 100
                rounded = number.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
            return {"kind": "coarse_decimal", "value": format(abs(rounded) if not rounded else rounded, "f")}
        except InvalidOperation:
            pass
    return cell


def coarse_cell(cell, rule):
    kind, value = cell["kind"], cell.get("value")
    if isinstance(rule, (tuple, list)):
        return _text_number(cell, *rule)
    if rule == "empty" and (kind == "null" or (kind == "string" and value == "")):
        return {"kind": "coarse_empty"}
    if rule == "date" and kind in {"date", "datetime", "string"}:
        match = _DATE_VALUE.fullmatch(value)
        if match:
            try:
                day = date.fromisoformat(match[1])
            except ValueError:
                return cell
            return {"kind": "coarse_date", "value": day.isoformat()}
    if isinstance(rule, int) and kind in _NUMERIC_KINDS:
        try:
            number = Decimal(str(float.fromhex(value))) if kind == "float" else Decimal(value)
            return _scaled_number(cell, number, rule)
        except (InvalidOperation, OverflowError, ValueError):
            pass
    return cell


def coarse_snapshot(snapshot, rules):
    columns = [(index, rules[name]) for index, name in enumerate(snapshot["columns"]) if name in rules]
    rows = [row.copy() for row in snapshot["rows"]]
    for row in rows:
        for index, rule in columns:
            if index < len(row):
                row[index] = coarse_cell(row[index], rule)
    return {**snapshot, "rows": rows}

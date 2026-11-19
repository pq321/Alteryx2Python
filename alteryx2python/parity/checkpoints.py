"""Presentation rules for comparing captured data without modifying records."""

from collections import Counter
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
import re

from alteryx2python.expressions.lexer import tokenize


_TEXT_TYPES = {"String", "WString", "V_String", "V_WString"}
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


def coarse_rules(snapshot, protected):
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
        elif dtype in _TEXT_TYPES and name.casefold() not in protected:
            rules[name] = "empty"
    return rules


def coarse_cell(cell, rule):
    kind, value = cell["kind"], cell.get("value")
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
    if isinstance(rule, int) and kind in {"int", "decimal", "float"}:
        try:
            number = Decimal(str(float.fromhex(value))) if kind == "float" else Decimal(value)
            if number.is_finite():
                with localcontext() as context:
                    context.prec = 100
                    rounded = number.quantize(Decimal(1).scaleb(-rule), rounding=ROUND_HALF_UP)
                return {"kind": "coarse_decimal", "value": format(abs(rounded) if not rounded else rounded, "f")}
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

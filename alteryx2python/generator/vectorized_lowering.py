"""Vectorized Pandas and clean scalar Python lowering for Phase 2 expressions."""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Callable

from alteryx2python.expressions.ast import (
    BinaryExpression,
    ConditionalExpression,
    ExpressionNode,
    FieldReference,
    FunctionExpression,
    LiteralExpression,
    UnaryExpression,
)
from alteryx2python.expressions.numeric import as_formula_series
from alteryx2python.generator.parameters import ParameterExpression


STRING_RETURNING_FUNCS = frozenset({
    "TRIM", "TRIMLEFT", "TRIMRIGHT", "UPPERCASE", "LOWERCASE", "TITLECASE",
    "LEFT", "RIGHT", "SUBSTRING", "REPLACE", "TOSTRING", "DATETIMEFORMAT", "FILEADDPATHS",
})
BOOL_RETURNING_FUNCS = frozenset({
    "ISNULL", "ISEMPTY", "CONTAINS", "STARTSWITH", "ENDSWITH",
})
NUMERIC_RETURNING_FUNCS = frozenset({
    "TONUMBER", "ABS", "CEIL", "FLOOR", "LENGTH", "ROUND",
})


@dataclass
class LoweredExpr:
    code: str
    is_series: bool
    kind: str  # "string" | "numeric" | "bool" | "any"
    imports: set[str] = field(default_factory=set)
    nullable_bool: bool = False


def _resolve_special_ref(
    node: FieldReference,
    param_names: dict[str, str],
    static_constants: dict[str, Any],
) -> tuple[str, str] | None:
    """Resolve explicit Question.* / User.* / Engine.* token references (bare names are record columns)."""
    clean = node.name.strip("%")
    if not clean.startswith(("Question.", "User.", "Engine.")):
        return None
    if clean in param_names:
        return param_names[clean], "any"
    if clean.startswith("Question.") and clean[9:] in param_names:
        return param_names[clean[9:]], "any"
    if clean in static_constants:
        val = static_constants[clean]
        kind = "string" if isinstance(val, str) else ("bool" if isinstance(val, bool) else ("numeric" if isinstance(val, (int, float)) else "any"))
        return repr(val), kind
    return None


def _infer_param_kind(py_name: str, param_meta: dict[str, dict[str, Any]]) -> str:
    meta = param_meta.get(py_name, {})
    q_kind = meta.get("kind", "")
    if q_kind in {"BooleanGroup", "CheckBoxGroup", "RadioGroup", "RadioButtonGroup"}:
        return "bool"
    if q_kind == "NumericUpDown":
        return "numeric"
    if q_kind in {"TextBox", "QuestionTextBox", "Date", "DropDown", "FileBrowse", "QuestionFileBrowse", "FolderBrowse"}:
        return "string"
    return "any"


def _ensure_bool_mask(expr: LoweredExpr, *, na_default: bool = False) -> tuple[str, set[str]]:
    if not expr.is_series:
        return f"bool({expr.code})", set(expr.imports)
    if expr.nullable_bool or expr.kind != "bool":
        code = expr.code
        if not (code.startswith("(") and code.endswith(")")) and " " in code:
            code = f"({code})"
        return f"{code}.fillna({na_default!r}).astype(bool)", set(expr.imports)
    return expr.code, set(expr.imports)


def _power_of_ten_decimals(multiple: float) -> int | None:
    if multiple <= 0 or not math.isfinite(multiple):
        return None
    log10 = -math.log10(multiple)
    rounded = round(log10)
    if abs(log10 - rounded) < 1e-9 and rounded >= 0:
        return int(rounded)
    return None


def try_lower_vectorized(
    expression: ExpressionNode,
    frame_var: str,
    *,
    param_names: dict[str, str] | None = None,
    param_meta: dict[str, dict[str, Any]] | None = None,
    static_constants: dict[str, Any] | None = None,
    known_column_kinds: dict[str, str] | None = None,
    casefold_comparisons: bool = False,
    link: Callable | None = None,
) -> LoweredExpr | None:
    """Lower ExpressionNode to vectorized Pandas / clean scalar Python, or None if unsupported."""
    param_names = param_names or {}
    param_meta = param_meta or {}
    static_constants = static_constants or {}
    known_column_kinds = {k.casefold(): v for k, v in (known_column_kinds or {}).items()}

    def arithmetic_code(operand: LoweredExpr) -> str:
        if link is not None and operand.is_series and operand.kind == "any":
            return f"{link(as_formula_series)}({operand.code})"
        return operand.code

    def lower(node: ExpressionNode) -> LoweredExpr | None:
        if isinstance(node, LiteralExpression):
            val = node.value
            if val is None:
                return LoweredExpr("None", is_series=False, kind="any")
            if isinstance(val, bool):
                return LoweredExpr(repr(val), is_series=False, kind="bool")
            if isinstance(val, (int, float)):
                return LoweredExpr(repr(val), is_series=False, kind="numeric")
            if isinstance(val, str):
                return LoweredExpr(repr(val), is_series=False, kind="string")
            return LoweredExpr(repr(val), is_series=False, kind="any")

        if isinstance(node, ParameterExpression):
            py_name = param_names.get(node.name, node.name)
            return LoweredExpr(py_name, is_series=False, kind=_infer_param_kind(py_name, param_meta))

        if isinstance(node, FieldReference):
            special = _resolve_special_ref(node, param_names, static_constants)
            if special is not None:
                code, s_kind = special
                if s_kind == "any" and code in param_meta:
                    s_kind = _infer_param_kind(code, param_meta)
                return LoweredExpr(code, is_series=False, kind=s_kind)
            # Row-offset references (MultiRowFormula) cannot lower as plain column Series
            if node.name.startswith(("Row-", "Row+")) or node.name == "_CurrentField_":
                return None
            c_kind = known_column_kinds.get(node.name.casefold(), "any")
            if c_kind == "decimal":
                return None
            return LoweredExpr(
                f"{frame_var}[{node.name!r}]",
                is_series=True,
                kind=c_kind,
                nullable_bool=(c_kind == "bool"),
            )

        if isinstance(node, UnaryExpression):
            inner = lower(node.operand)
            if inner is None:
                return None
            if node.operator == "!":
                if not inner.is_series:
                    code = f"(not {inner.code})" if inner.kind == "bool" else f"(not bool({inner.code}))"
                    return LoweredExpr(code, is_series=False, kind="bool", imports=set(inner.imports))
                mask, imps = _ensure_bool_mask(inner, na_default=False)
                return LoweredExpr(f"(~{mask})", is_series=True, kind="bool", imports=imps)
            if node.operator in {"-", "+"}:
                return LoweredExpr(
                    f"({node.operator}{inner.code})",
                    is_series=inner.is_series,
                    kind="numeric",
                    imports=set(inner.imports),
                )
            return None

        if isinstance(node, BinaryExpression):
            left = lower(node.left)
            right = lower(node.right)
            if left is None or right is None:
                return None
            imps = set(left.imports) | set(right.imports)
            op = node.operator
            either_series = left.is_series or right.is_series

            if op in {"AND", "OR"}:
                if not either_series:
                    py_op = "and" if op == "AND" else "or"
                    l_code = left.code if left.kind == "bool" else f"bool({left.code})"
                    r_code = right.code if right.kind == "bool" else f"bool({right.code})"
                    return LoweredExpr(f"({l_code} {py_op} {r_code})", is_series=False, kind="bool", imports=imps)
                bit_op = "&" if op == "AND" else "|"
                if left.is_series and right.is_series:
                    lm, li = _ensure_bool_mask(left)
                    rm, ri = _ensure_bool_mask(right)
                    return LoweredExpr(f"({lm} {bit_op} {rm})", is_series=True, kind="bool", imports=imps | li | ri)
                # One Series, one scalar bool parameter!
                s_side, p_side = (left, right) if left.is_series else (right, left)
                sm, si = _ensure_bool_mask(s_side)
                p_bool = p_side.code if p_side.kind == "bool" else f"bool({p_side.code})"
                return LoweredExpr(f"({sm} {bit_op} {p_bool})", is_series=True, kind="bool", imports=imps | si)

            if op == "+":
                is_str_concat = left.kind == "string" or right.kind == "string"
                if is_str_concat:
                    def as_str_part(part: LoweredExpr) -> str:
                        if part.kind == "string":
                            return part.code
                        if part.is_series:
                            return f'{part.code}.astype("string")'
                        return f"str({part.code})"

                    return LoweredExpr(
                        f"({as_str_part(left)} + {as_str_part(right)})",
                        is_series=either_series,
                        kind="string",
                        imports=imps,
                    )
            if op in {"+", "-", "*", "/"}:
                code = f"({arithmetic_code(left)} {op} {arithmetic_code(right)})"
                return LoweredExpr(code, is_series=either_series, kind="numeric", imports=imps)

            if op in {"=", "==", "!=", "<", "<=", ">", ">="}:
                py_cmp = "==" if op == "=" else op
                if not either_series:
                    if casefold_comparisons and (left.kind == "string" or right.kind == "string") and py_cmp in {"==", "!="}:
                        return LoweredExpr(
                            f"(str({left.code}).casefold() {py_cmp} str({right.code}).casefold())",
                            is_series=False,
                            kind="bool",
                            imports=imps,
                        )
                    return LoweredExpr(f"({left.code} {py_cmp} {right.code})", is_series=False, kind="bool", imports=imps)

                na_val = py_cmp == "!="
                # Prefer idiomatic Series methods (.eq / .ne / .gt / .ge / .lt / .le) when left is Series & right is scalar
                method_map = {"==": "eq", "!=": "ne", "<": "lt", "<=": "le", ">": "gt", ">=": "ge"}
                if left.is_series and not right.is_series:
                    if right.code == "None":
                        code = f"{left.code}.notna()" if py_cmp == "!=" else f"{left.code}.isna()"
                        return LoweredExpr(code, is_series=True, kind="bool", imports=imps)
                    if casefold_comparisons and (left.kind == "string" or right.kind == "string") and py_cmp in {"==", "!="}:
                        r_cf = repr(str(node.right.value).casefold()) if isinstance(node.right, LiteralExpression) else f"str({right.code}).casefold()"
                        code = f'{left.code}.astype("string").str.casefold().{method_map[py_cmp]}({r_cf}).fillna({na_val!r})'
                        return LoweredExpr(code, is_series=True, kind="bool", imports=imps)
                    code = f"{left.code}.{method_map[py_cmp]}({right.code})"
                    return LoweredExpr(code, is_series=True, kind="bool", imports=imps, nullable_bool=True)

                if casefold_comparisons and (left.kind == "string" or right.kind == "string") and py_cmp in {"==", "!="}:
                    l_cf = f'{left.code}.astype("string").str.casefold()' if left.is_series else f"str({left.code}).casefold()"
                    r_cf = f'{right.code}.astype("string").str.casefold()' if right.is_series else f"str({right.code}).casefold()"
                    return LoweredExpr(
                        f"({l_cf} {py_cmp} {r_cf}).fillna({na_val!r})",
                        is_series=True,
                        kind="bool",
                        imports=imps,
                    )
                return LoweredExpr(
                    f"({left.code} {py_cmp} {right.code})",
                    is_series=True,
                    kind="bool",
                    imports=imps,
                    nullable_bool=True,
                )

            return None

        if isinstance(node, ConditionalExpression):
            # Flatten nested ConditionalExpressions for np.select when conditions are Series
            branches: list[tuple[LoweredExpr, LoweredExpr]] = []
            cursor: ExpressionNode = node
            while isinstance(cursor, ConditionalExpression):
                c_low = lower(cursor.condition)
                t_low = lower(cursor.true_value)
                if c_low is None or t_low is None:
                    return None
                branches.append((c_low, t_low))
                cursor = cursor.false_value
            else_low = lower(cursor)
            if else_low is None:
                return None

            imps = set(else_low.imports)
            for c_low, t_low in branches:
                imps |= c_low.imports | t_low.imports

            # Pure scalar condition chain (e.g., IF detail AND !summary THEN df["amount"] ELSE 0)
            if len(branches) == 1 and not branches[0][0].is_series:
                c_low, t_low = branches[0]
                cond_code = c_low.code if c_low.kind == "bool" else f"bool({c_low.code})"
                result_kind = t_low.kind if t_low.kind == else_low.kind else "any"
                return LoweredExpr(
                    f"({t_low.code} if {cond_code} else {else_low.code})",
                    is_series=(t_low.is_series or else_low.is_series),
                    kind=result_kind,
                    imports=imps,
                )

            imps.add("import numpy as np")
            if len(branches) == 1:
                c_low, t_low = branches[0]
                cm, ci = _ensure_bool_mask(c_low)
                imps |= ci
                result_kind = t_low.kind if t_low.kind == else_low.kind else "any"
                return LoweredExpr(
                    f"pd.Series(np.where({cm}, {t_low.code}, {else_low.code}), index={frame_var}.index)",
                    is_series=True,
                    kind=result_kind,
                    imports=imps,
                )

            cond_codes: list[str] = []
            choice_codes: list[str] = []
            for c_low, t_low in branches:
                if c_low.is_series:
                    cm, ci = _ensure_bool_mask(c_low)
                    imps |= ci
                    cond_codes.append(cm)
                else:
                    cond_codes.append(f"pd.Series({c_low.code!s}, index={frame_var}.index, dtype=bool)")
                choice_codes.append(t_low.code)
            return LoweredExpr(
                f"pd.Series(np.select([{', '.join(cond_codes)}], [{', '.join(choice_codes)}], default={else_low.code}), index={frame_var}.index)",
                is_series=True,
                kind="any",
                imports=imps,
            )

        if isinstance(node, FunctionExpression):
            fn = node.name.upper()
            lowered_args = [lower(a) for a in node.args]
            if any(a is None for a in lowered_args):
                return None
            args = [a for a in lowered_args if a is not None]
            imps = {imp for a in args for imp in a.imports}
            any_series = any(a.is_series for a in args)

            if fn == "NULL" and len(args) == 0:
                return LoweredExpr("pd.NA", is_series=False, kind="any")

            if fn in {"DATETIMENOW", "DATETIMETODAY"} and len(args) == 0:
                as_of_var = param_names.get("__as_of__", "None")
                imps.add("from datetime import datetime")
                fmt = "%Y-%m-%d %H:%M:%S" if fn == "DATETIMENOW" else "%Y-%m-%d"
                code = f"(pd.Timestamp({as_of_var}).strftime({fmt!r}) if {as_of_var} else datetime.now().strftime({fmt!r}))"
                return LoweredExpr(code, is_series=False, kind="string", imports=imps)

            if fn == "ISNULL" and len(args) == 1:
                a0 = args[0]
                if a0.is_series:
                    return LoweredExpr(f"{a0.code}.isna()", is_series=True, kind="bool", imports=imps)
                return LoweredExpr(f"pd.isna({a0.code})", is_series=False, kind="bool", imports=imps)

            if fn == "ISEMPTY" and len(args) == 1:
                a0 = args[0]
                if a0.is_series:
                    return LoweredExpr(f'({a0.code}.isna() | {a0.code}.astype("string").eq(""))', is_series=True, kind="bool", imports=imps)
                return LoweredExpr(f"({a0.code} is None or str({a0.code}) == '')", is_series=False, kind="bool", imports=imps)

            if fn in {"TRIM", "TRIMLEFT", "TRIMRIGHT", "UPPERCASE", "LOWERCASE", "TITLECASE"} and len(args) == 1:
                a0 = args[0]
                str_method = {
                    "TRIM": "strip()",
                    "TRIMLEFT": "lstrip()",
                    "TRIMRIGHT": "rstrip()",
                    "UPPERCASE": "upper()",
                    "LOWERCASE": "lower()",
                    "TITLECASE": "title()",
                }[fn]
                if a0.is_series:
                    base = a0.code if a0.kind == "string" else f'{a0.code}.astype("string")'
                    return LoweredExpr(f"{base}.str.{str_method}", is_series=True, kind="string", imports=imps)
                return LoweredExpr(f"str({a0.code}).{str_method}", is_series=False, kind="string", imports=imps)

            if fn == "LENGTH" and len(args) == 1:
                a0 = args[0]
                if a0.is_series:
                    return LoweredExpr(f'{a0.code}.fillna("").astype(str).str.len()', is_series=True, kind="numeric", imports=imps)
                return LoweredExpr(f"len('' if {a0.code} is None else str({a0.code}))", is_series=False, kind="numeric", imports=imps)

            if fn == "LEFT" and len(args) == 2 and not args[1].is_series:
                a0, n_arg = args
                if a0.is_series:
                    base = a0.code if a0.kind == "string" else f'{a0.code}.astype("string")'
                    return LoweredExpr(f"{base}.str.slice(0, int({n_arg.code}))", is_series=True, kind="string", imports=imps)
                return LoweredExpr(f"str({a0.code})[:int({n_arg.code})]", is_series=False, kind="string", imports=imps)

            if fn == "RIGHT" and len(args) == 2 and not args[1].is_series:
                a0, n_arg = args
                if a0.is_series:
                    base = a0.code if a0.kind == "string" else f'{a0.code}.astype("string")'
                    return LoweredExpr(f"{base}.str.slice(-int({n_arg.code}))", is_series=True, kind="string", imports=imps)
                return LoweredExpr(f"str({a0.code})[-int({n_arg.code}):]", is_series=False, kind="string", imports=imps)

            if fn == "SUBSTRING" and len(args) == 3 and not args[1].is_series and not args[2].is_series:
                a0, start_arg, len_arg = args
                if a0.is_series:
                    base = a0.code if a0.kind == "string" else f'{a0.code}.astype("string")'
                    return LoweredExpr(
                        f"{base}.str.slice(int({start_arg.code}), int({start_arg.code}) + int({len_arg.code}))",
                        is_series=True,
                        kind="string",
                        imports=imps,
                    )
                return LoweredExpr(
                    f"str({a0.code})[int({start_arg.code}):int({start_arg.code}) + int({len_arg.code})]",
                    is_series=False,
                    kind="string",
                    imports=imps,
                )

            if fn == "REPLACE" and len(args) == 3 and not args[1].is_series and not args[2].is_series:
                a0, pat_arg, rep_arg = args
                if a0.is_series:
                    base = a0.code if a0.kind == "string" else f'{a0.code}.astype("string")'
                    return LoweredExpr(
                        f"{base}.str.replace({pat_arg.code}, {rep_arg.code}, regex=False)",
                        is_series=True,
                        kind="string",
                        imports=imps,
                    )
                return LoweredExpr(f"str({a0.code}).replace({pat_arg.code}, {rep_arg.code})", is_series=False, kind="string", imports=imps)

            if fn == "CONTAINS" and len(args) in {2, 3} and not args[1].is_series:
                a0, sub_arg = args[0], args[1]
                case_ins = True
                if len(args) == 3 and isinstance(node.args[2], LiteralExpression):
                    case_ins = bool(node.args[2].value)
                elif len(args) == 3:
                    return None
                if a0.is_series:
                    base = a0.code if a0.kind == "string" else f'{a0.code}.astype("string")'
                    return LoweredExpr(
                        f"{base}.str.contains({sub_arg.code}, case={not case_ins!r}, regex=False, na=False)",
                        is_series=True,
                        kind="bool",
                        imports=imps,
                    )
                return None

            if fn in {"STARTSWITH", "ENDSWITH"} and len(args) == 2 and not args[1].is_series:
                a0, sub_arg = args[0], args[1]
                m = "startswith" if fn == "STARTSWITH" else "endswith"
                if a0.is_series:
                    return LoweredExpr(
                        f'{a0.code}.astype("string").str.lower().str.{m}(str({sub_arg.code}).lower()).fillna(False)',
                        is_series=True,
                        kind="bool",
                        imports=imps,
                    )
                return LoweredExpr(
                    f"str({a0.code}).lower().{m}(str({sub_arg.code}).lower())",
                    is_series=False,
                    kind="bool",
                    imports=imps,
                )

            if fn == "TONUMBER" and len(args) >= 1:
                if len(args) > 1:
                    return None
                a0 = args[0]
                if a0.is_series:
                    return LoweredExpr(f'pd.to_numeric({a0.code}, errors="coerce")', is_series=True, kind="numeric", imports=imps)
                return LoweredExpr(f"float({a0.code})", is_series=False, kind="numeric", imports=imps)

            if fn == "TOSTRING" and len(args) == 1:
                a0 = args[0]
                if a0.is_series:
                    return LoweredExpr(f'{a0.code}.astype("string")', is_series=True, kind="string", imports=imps)
                return LoweredExpr(f"str({a0.code})", is_series=False, kind="string", imports=imps)

            if fn == "ABS" and len(args) == 1:
                a0 = args[0]
                code = f"{a0.code}.abs()" if a0.is_series else f"abs({a0.code})"
                return LoweredExpr(code, is_series=a0.is_series, kind="numeric", imports=imps)

            if fn == "ROUND" and len(args) == 2 and isinstance(node.args[1], LiteralExpression):
                mult = node.args[1].value
                if isinstance(mult, (int, float)):
                    decimals = _power_of_ten_decimals(float(mult))
                    if decimals is not None and args[0].is_series:
                        # Use half-away-from-zero safe fallback if needed; keep scalar fallback for exact Alteryx tie-breaking
                        return None
                return None

            if fn == "DATETIMEFORMAT" and len(args) == 2 and not args[1].is_series:
                a0, fmt_arg = args
                if a0.is_series:
                    return LoweredExpr(
                        f'pd.to_datetime({a0.code}, errors="coerce").dt.strftime({fmt_arg.code})',
                        is_series=True,
                        kind="string",
                        imports=imps,
                    )
                return LoweredExpr(
                    f'(pd.Timestamp({a0.code}).strftime({fmt_arg.code}) if {a0.code} else None)',
                    is_series=False,
                    kind="string",
                    imports=imps,
                )

            if fn == "FILEADDPATHS" and len(args) == 2:
                imps.add("import ntpath")
                a0, a1 = args
                s0 = a0.code if a0.kind == "string" else f"str({a0.code})"
                s1 = a1.code if a1.kind == "string" else f"str({a1.code})"
                if not any_series:
                    return LoweredExpr(f"ntpath.join({s0}, {s1})", is_series=False, kind="string", imports=imps)
                if a0.is_series and not a1.is_series:
                    return LoweredExpr(
                        f"{a0.code}.map(lambda p: None if pd.isna(p) else ntpath.join(str(p), {s1}))",
                        is_series=True,
                        kind="string",
                        imports=imps,
                    )
                if not a0.is_series and a1.is_series:
                    return LoweredExpr(
                        f"{a1.code}.map(lambda p: None if pd.isna(p) else ntpath.join({s0}, str(p)))",
                        is_series=True,
                        kind="string",
                        imports=imps,
                    )

            return None

        return None

    return lower(expression)

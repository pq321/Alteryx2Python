"""Compile optimized WorkflowIR into a config-decoupled, idiomatic Python package."""

from __future__ import annotations

import ast
from copy import deepcopy
from dataclasses import asdict, dataclass, field
import hashlib
import inspect
import json
import keyword
from pathlib import Path
import re
import textwrap
from typing import Any

import pandas as pd

from alteryx2python.expressions.errors import UnsupportedExpressionError
from alteryx2python.expressions.parser import parse_expression
from alteryx2python.generator.config_extractor import ConfigSpec, extract_config
from alteryx2python.generator.ir_optimizer import (
    LoopMacroSpec,
    MacroSubgraphSpec,
    OptimizationResult,
    optimize_workflow_ir,
)
from alteryx2python.generator.package_templates import (
    render_audit_utils_py,
    render_cli_py,
    render_init_py,
    render_io_utils_py,
    render_main_py,
    render_runner_py,
)
from alteryx2python.generator.parameters import ParameterExpression, prepare_parameters
from alteryx2python.generator.source_linker import (
    RemoveTracing,
    SourceLinker,
    UnsupportedLowering,
    simplify_template,
    strip_annotations,
)
from alteryx2python.generator.vectorized_lowering import _ensure_bool_mask, try_lower_vectorized
from alteryx2python.ir.models import NodeIR, WorkflowIR
from alteryx2python.tools.field_contracts import INTEGER_BYTES, STRING_TYPES, field_contract


PACKAGE_TEMPLATE_VERSION = "native-package/2.0.0"

IO_BOUNDARY_TOOLS = frozenset({
    "DbFileInput",
    "TextInput",
    "DbFileOutput",
    "PortfolioComposerRender",
    "Email",
})


def _ident(value: str, default: str = "step") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value)).strip("_").lower() or default
    if cleaned[0].isdigit() or keyword.iskeyword(cleaned):
        return f"{default}_{cleaned}"
    return cleaned


def _annotation_name(node: NodeIR) -> str:
    ann = node.metadata.get("annotation", {}).get("Name", "")
    if isinstance(ann, dict):
        ann = ann.get("text", "")
    return str(ann or "").strip()


@dataclass
class PackageArtifact:
    """Self-contained generated Python package files and sidecar metadata."""

    files: dict[str, str]
    manifest: dict[str, Any]
    workflow: WorkflowIR
    config_spec: ConfigSpec
    entrypoint: str = "pipeline.py"

    @property
    def source(self) -> str:
        return self.files[self.entrypoint]

    @property
    def config_toml(self) -> str:
        return self.files["config.toml"]

    def write(self, destination: str | Path) -> list[Path]:
        dest = Path(destination)
        if dest.exists() and any(dest.iterdir() if dest.is_dir() else [dest]):
            raise FileExistsError(f"Use a fresh destination; target already exists: {dest}")
        dest.mkdir(parents=True, exist_ok=True)
        written: list[Path] = []
        for rel_posix, content in sorted(self.files.items()):
            target = dest / Path(rel_posix)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8", newline="")
            written.append(target)
        manifest_path = dest / "manifest.json"
        ir_path = dest / "workflow.ir.json"
        manifest_path.write_text(json.dumps(self.manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        ir_path.write_text(json.dumps(asdict(self.workflow), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.extend([manifest_path, ir_path])
        return written


@dataclass
class _CompiledOp:
    node_id: str
    source_tool_id: str
    tool_type: str
    func_name: str
    input_vars: dict[str, str]  # anchor_name -> pipeline var name
    arg_names: dict[str, str]   # anchor_name -> function parameter name
    output_anchors: tuple[str, ...]
    output_vars: list[str]
    param_kwargs: list[str]     # sorted python parameter names from config["parameters"]
    runtime_kwargs: list[str]
    body_lines: list[str]
    imports: set[str] = field(default_factory=set)
    can_inline_linear: bool = False
    guards: list[str] = field(default_factory=list)
    audit_label: str = ""
    audit_summary: str = ""


class _SubgraphEmitter:
    """Lower an optimized WorkflowIR into pure stage functions + orchestration lines."""

    def __init__(
        self,
        opt: OptimizationResult,
        config_spec: ConfigSpec,
        *,
        delivery_profile: str | None = None,
        helper_linker: SourceLinker | None = None,
        is_macro: bool = False,
    ) -> None:
        self.opt = opt
        self.workflow = opt.workflow
        self.config_spec = config_spec
        self.delivery_profile = delivery_profile
        self.linker = helper_linker if helper_linker is not None else SourceLinker()
        self.is_macro = is_macro
        self.pipeline_imports: set[str] = {"from __future__ import annotations", "import pandas as pd"}
        self.stage_defs: list[tuple[str, list[str], str]] = []  # (func_name, source_node_ids, code)
        self.has_messages = False
        self.needs_commands = False
        self.needs_render_html = False
        self.needs_render_xlsx = False
        self.needs_email = False
        self.needs_file_exists = False
        self.expression_needs_file_exists = False
        self.needs_excel_in = any(v.get("format") == "excel" for v in config_spec.inputs.values())
        self.needs_excel_out = any(v.get("format") == "excel" for v in config_spec.outputs.values())
        self.column_kinds_by_var: dict[str, dict[str, str]] = {}

    def _scalar_expression(self, expr, param_names: dict[str, str], static_consts: dict[str, Any]) -> str:
        from alteryx2python.expressions.ast import (
            BinaryExpression,
            ConditionalExpression,
            FieldReference,
            FunctionExpression,
            LiteralExpression,
            UnaryExpression,
        )
        from alteryx2python.expressions.functions import FUNCTION_REGISTRY
        from alteryx2python.expressions.numeric import add_nullable, arithmetic_operand, as_formula_value

        def render(node) -> str:
            if isinstance(node, ParameterExpression):
                return param_names.get(node.name, node.name)
            if isinstance(node, LiteralExpression):
                return repr(node.value)
            if isinstance(node, FieldReference):
                clean = node.name.strip("%")
                if clean.startswith(("Question.", "User.", "Engine.")):
                    if clean in param_names:
                        return f"row.get({node.name!r}, {param_names[clean]})"
                    if clean.startswith("Question.") and clean[9:] in param_names:
                        return f"row.get({node.name!r}, {param_names[clean[9:]]})"
                    if clean in static_consts:
                        return f"row.get({node.name!r}, {static_consts[clean]!r})"
                return f"row[{node.name!r}]"
            if isinstance(node, ConditionalExpression):
                return f"({render(node.true_value)} if bool({render(node.condition)}) else {render(node.false_value)})"
            if isinstance(node, UnaryExpression) and node.operator == "!":
                return f"(not bool({render(node.operand)}))"
            if isinstance(node, UnaryExpression) and node.operator in {"-", "+"}:
                return f"({node.operator}{render(node.operand)})"
            if isinstance(node, FunctionExpression):
                fn_up = node.name.upper()
                if fn_up == "FILEEXISTS" and len(node.args) == 1:
                    self.expression_needs_file_exists = True
                    return f"operations['file_exists']({render(node.args[0])})"
                if fn_up in {"TRIMLEFT", "TRIMRIGHT", "LOWERCASE"} and len(node.args) == 1:
                    arg_code = render(node.args[0])
                    m = {"TRIMLEFT": "lstrip()", "TRIMRIGHT": "rstrip()", "LOWERCASE": "lower()"}[fn_up]
                    return f"(None if pd.isna(_v := {arg_code}) else str(_v).{m})"
                if fn_up == "TONUMBER" and len(node.args) == 1:
                    arg_code = render(node.args[0])
                    return f"(None if pd.isna(_v := {arg_code}) or str(_v).strip() == '' else float(_v))"
                if fn_up == "ABS" and len(node.args) == 1:
                    arg_code = render(node.args[0])
                    return f"(None if pd.isna(_v := {arg_code}) else abs(float(_v)))"
                if fn_up == "LENGTH" and len(node.args) == 1:
                    arg_code = render(node.args[0])
                    return f"(0 if pd.isna(_v := {arg_code}) else len(str(_v)))"
                fn = FUNCTION_REGISTRY.get(fn_up)
                if fn is None:
                    raise UnsupportedLowering(f"Unknown expression function: {node.name}")
                h_name = self.linker.function(fn)
                if fn_up in {"DATETIMENOW", "DATETIMETODAY"}:
                    as_of_var = param_names.get("__as_of__", "None")
                    return f"{h_name}({as_of_var} or None)"
                return f"{h_name}(" + ", ".join(render(a) for a in node.args) + ")"
            if isinstance(node, BinaryExpression):
                left, right = render(node.left), render(node.right)
                op = node.operator
                if op in {"AND", "OR"}:
                    return f"(bool({left}) {op.lower()} bool({right}))"
                if op == "+":
                    return f"{self.linker.function(add_nullable)}({left}, {right})"
                if op in {"-", "*", "/"}:
                    h_op = self.linker.function(arithmetic_operand)
                    l_code = left if isinstance(node.left, LiteralExpression) and node.left.value is not None else f"{h_op}({left})"
                    r_code = right if isinstance(node.right, LiteralExpression) and node.right.value is not None else f"{h_op}({right})"
                    return f"({l_code} {op} {r_code})"
                h_val = self.linker.function(as_formula_value)
                lv = left if isinstance(node.left, LiteralExpression) else f"{h_val}({left})"
                rv = right if isinstance(node.right, LiteralExpression) else f"{h_val}({right})"
                if op in {">", ">=", "<", "<="}:
                    if (isinstance(node.left, LiteralExpression) and node.left.value is None) or (
                        isinstance(node.right, LiteralExpression) and node.right.value is None
                    ):
                        return "False"
                    checks = [
                        f"{code} is not None"
                        for part, code in ((node.left, left), (node.right, right))
                        if not isinstance(part, LiteralExpression)
                    ]
                    return "(" + " and ".join([*checks, f"{lv} {op} {rv}"]) + ")"
                if op in {"=", "==", "!="}:
                    py_op = "==" if op == "=" else op
                    return f"({lv} {py_op} {rv})"
            raise UnsupportedLowering(f"Unsupported expression AST: {type(node).__name__}")

        return render(expr)

    def _collect_expr_params(self, expr, param_names: dict[str, str]) -> set[str]:
        from dataclasses import fields as dc_fields, is_dataclass
        from alteryx2python.expressions.ast import FieldReference, FunctionExpression

        found: set[str] = set()

        def visit(node) -> None:
            if isinstance(node, ParameterExpression):
                if node.name in param_names:
                    found.add(param_names[node.name])
                return
            if isinstance(node, FieldReference):
                clean = node.name.strip("%")
                if clean.startswith(("Question.", "User.", "Engine.")):
                    if clean in param_names:
                        found.add(param_names[clean])
                    elif clean.startswith("Question.") and clean[9:] in param_names:
                        found.add(param_names[clean[9:]])
                return
            if isinstance(node, FunctionExpression) and node.name.upper() in {"DATETIMENOW", "DATETIMETODAY"}:
                if "__as_of__" in param_names:
                    found.add(param_names["__as_of__"])
            if is_dataclass(node):
                for f in dc_fields(node):
                    val = getattr(node, f.name)
                    if is_dataclass(val):
                        visit(val)
                    elif isinstance(val, list):
                        for item in val:
                            if is_dataclass(item):
                                visit(item)

        visit(expr)
        return found

    def _native_cast_expr(
        self,
        series_code: str,
        dtype: str | None,
        size: Any = None,
    ) -> tuple[str, str]:
        """Return (cast_code, kind_tag) using clean native Pandas by default."""
        if not dtype:
            return series_code, "any"

        if dtype in STRING_TYPES:
            code = f'{series_code}.astype("string")'
            contract = field_contract(dtype, size)
            if contract and contract.get("size"):
                code = f"{code}.str.slice(0, {contract['size']!r})"
            return code, "string"

        if dtype in INTEGER_BYTES or dtype == "int64":
            if dtype in INTEGER_BYTES:
                from alteryx2python.tools.field_contracts import coerce_field

                h_coerce = self.linker.function(coerce_field)
                return f"{h_coerce}({series_code}, {dtype!r}, {size!r})", "numeric"
            target = "UInt8" if dtype == "Byte" else ("Int64" if dtype == "int64" else dtype)
            return f'pd.to_numeric({series_code}, errors="coerce").astype({target!r})', "numeric"

        if dtype in {"Float", "Double", "float64"}:
            target = "float32" if dtype == "Float" else "float64"
            return f'pd.to_numeric({series_code}, errors="coerce").astype({target!r})', "numeric"

        if dtype == "FixedDecimal":
            contract = field_contract(dtype, size)
            width = str((contract or {}).get("size") or size or "19.2")
            _, _, scale_str = width.partition(".")
            scale = int(scale_str or "2")
            from alteryx2python.tools.field_contracts import _fixed_decimal

            prec = int(width.partition(".")[0] or "19")
            h_dec = self.linker.function(_fixed_decimal)
            return f"pd.Series([{h_dec}(v, {prec}, {scale}) for v in {series_code}], index={series_code}.index, dtype=object)", "decimal"

        if dtype in {"Bool", "bool"}:
            return (
                f"{series_code}.map(lambda v: pd.NA if pd.isna(v) else (v if isinstance(v, bool) else str(v).strip().lower() in ('true', '1'))).astype('boolean')",
                "bool",
            )

        formats = {"Date": "%Y-%m-%d", "DateTime": "%Y-%m-%d %H:%M:%S", "Time": "%H:%M:%S"}
        if dtype in formats:
            return f'pd.to_datetime({series_code}, errors="coerce").dt.strftime({formats[dtype]!r}).astype("string")', "string"

        raise UnsupportedLowering(f"Unsupported declared field type: {dtype}")

    def _lower_pure_node(
        self,
        node: NodeIR,
        cfg: dict[str, Any],
        arg_names: dict[str, str],
        input_vars: dict[str, str],
        consumed_anchors: set[str],
        outputs: tuple[str, ...],
        param_names: dict[str, str],
        static_consts: dict[str, Any],
    ) -> tuple[list[str], set[str], set[str], list[str], bool, dict[str, str]] | None:
        """Return (body_lines, imports, param_kwargs, runtime_kwargs, can_inline, out_col_kinds) or None."""
        kind = node.tool_type
        frame = next(iter(arg_names.values()), "df")
        in_var = next(iter(input_vars.values()), "")
        in_kinds = dict(self.column_kinds_by_var.get(in_var, {}))
        imps: set[str] = set()
        params_used: set[str] = set()

        if kind == "Select":
            from alteryx2python.tools.select import _expected_output_columns, _normalize_select_fields

            fields_list = _normalize_select_fields(cfg)
            unknown = any(f["source"] == "*Unknown" and f["selected"] for f in fields_list)
            selected = [f for f in fields_list if f["selected"] and f["source"] != "*Unknown"]
            explicit_sources = [f["source"] for f in fields_list if f["source"] != "*Unknown"]
            out_kinds: dict[str, str] = {}

            if not unknown:
                pure_subset = all(
                    f["rename"] == f["source"]
                    and not f["dtype"]
                    for f in selected
                )
                order = _expected_output_columns(cfg.get("expected_output_schema"))
                cols = [f["rename"] for f in selected]
                if order:
                    cols = [c for c in order if c in cols] + [c for c in cols if c not in order]
                if pure_subset:
                    for c in cols:
                        if c in in_kinds:
                            out_kinds[c] = in_kinds[c]
                    return [f"return {frame}[{cols!r}].copy()"], imps, params_used, [], True, out_kinds

                col_exprs: list[str] = []
                for f in selected:
                    src, dst = f["source"], f["rename"]
                    cast_code, k_tag = self._native_cast_expr(
                        f"{frame}[{src!r}]", f["dtype"], f.get("size")
                    )
                    if cast_code == f"{frame}[{src!r}]":
                        cast_code += ".copy()"
                        k_tag = in_kinds.get(src, "any")
                    out_kinds[dst] = k_tag
                    col_exprs.append(f"{dst!r}: {cast_code}")
                lines = [f"out = pd.DataFrame({{{', '.join(col_exprs)}}}, index={frame}.index)"]
                if order:
                    lines.append(f"ordered = [c for c in {order!r} if c in out.columns]")
                    lines.append("out = out.reindex(columns=ordered + [c for c in out.columns if c not in ordered])")
                lines.append("return out")
                return lines, imps, params_used, [], True, out_kinds

            # Select with *Unknown enabled
            out_kinds.update(in_kinds)
            dropped = [f["source"] for f in fields_list if not f["selected"] and f["source"] != "*Unknown"]
            lines = [f"out = {frame}.copy()"]
            if dropped:
                lines.append(f"out = out.drop(columns=[c for c in {dropped!r} if c in out.columns])")
            renames = {f["source"]: f["rename"] for f in selected if f["rename"] != f["source"]}
            if renames:
                lines.append(f"out = out.rename(columns={renames!r})")
                for s_col, d_col in renames.items():
                    if s_col in out_kinds:
                        out_kinds[d_col] = out_kinds.pop(s_col)
            for f in selected:
                dst = f["rename"]
                if f["dtype"]:
                    cast_code, k_tag = self._native_cast_expr(
                        f"out[{dst!r}]", f["dtype"], f.get("size")
                    )
                    lines.append(f"out[{dst!r}] = {cast_code}")
                    out_kinds[dst] = k_tag
            lines.append("return out")
            return lines, imps, params_used, [], True, out_kinds

        if kind == "Formula":
            lines = [f"out = {frame}.copy()"]
            out_kinds = dict(in_kinds)
            for idx, f_entry in enumerate(cfg.get("formula_fields", [])):
                if not f_entry.get("enabled", True):
                    continue
                target_col = str(f_entry["field"])
                parsed = self.opt.parameter_expressions.get(
                    (node.node_id, ("formula_fields", idx, "expression"))
                ) or parse_expression(f_entry["expression"])
                params_used |= self._collect_expr_params(parsed, param_names)

                lowered = try_lower_vectorized(
                    parsed,
                    "out",
                    param_names=param_names,
                    param_meta=self.config_spec.parameter_meta,
                    static_constants=static_consts,
                    known_column_kinds=out_kinds,
                )
                if lowered is not None:
                    imps |= lowered.imports
                    lines.append(f"out[{target_col!r}] = {lowered.code}")
                    k_tag = lowered.kind
                else:
                    scalar_code = self._scalar_expression(parsed, param_names, static_consts)
                    lines.append(
                        f"out[{target_col!r}] = pd.Series([{scalar_code} for row in out.to_dict('records')], index=out.index, dtype=object)"
                    )
                    k_tag = "any"

                f_type = f_entry.get("type")
                if f_type:
                    cast_code, k_tag = self._native_cast_expr(
                        f"out[{target_col!r}]", f_type, f_entry.get("size")
                    )
                    if cast_code != f"out[{target_col!r}]":
                        lines.append(f"out[{target_col!r}] = {cast_code}")
                out_kinds[target_col] = k_tag

            lines.append("return out")
            return lines, imps, params_used, [], True, out_kinds

        if kind == "Filter":
            if cfg.get("unsupported_operator"):
                raise UnsupportedLowering(f"Unsupported Filter operator: {cfg['unsupported_operator']}")
            parsed = self.opt.parameter_expressions.get((node.node_id, ("expression",))) or parse_expression(cfg["expression"])
            params_used |= self._collect_expr_params(parsed, param_names)
            lowered = try_lower_vectorized(
                parsed,
                frame,
                param_names=param_names,
                param_meta=self.config_spec.parameter_meta,
                static_constants=static_consts,
                known_column_kinds=in_kinds,
            )
            if lowered is not None:
                imps |= lowered.imports
                if lowered.is_series:
                    mask_code, mask_imps = _ensure_bool_mask(lowered)
                    imps |= mask_imps
                    lines = [f"mask = {mask_code}"]
                else:
                    lines = [f"mask = pd.Series(bool({lowered.code}), index={frame}.index, dtype=bool)"]
            else:
                scalar_code = self._scalar_expression(parsed, param_names, static_consts)
                lines = [f"mask = pd.Series([bool({scalar_code}) for row in {frame}.to_dict('records')], index={frame}.index, dtype=bool)"]

            want_true = "True" in consumed_anchors or not consumed_anchors
            want_false = "False" in consumed_anchors
            if want_true and not want_false:
                lines.append(f"return {frame}.loc[mask].copy()")
                return lines, imps, params_used, [], True, dict(in_kinds)
            if want_false and not want_true:
                lines.append(f"return {frame}.loc[~mask].copy()")
                return lines, imps, params_used, [], True, dict(in_kinds)
            lines.append(f"return {frame}.loc[mask].copy(), {frame}.loc[~mask].copy()")
            return lines, imps, params_used, [], False, dict(in_kinds)

        if kind == "Sort":
            from alteryx2python.tools.sort import _is_ascending

            s_fields = cfg.get("sort_fields", [])
            if not s_fields:
                raise UnsupportedLowering("Sort requires fields")
            keys = [f["field"] for f in s_fields]
            dirs = [_is_ascending(f.get("order", "Ascending")) for f in s_fields]
            asc = dirs[0] if all(d == dirs[0] for d in dirs) else dirs
            return (
                [f'return {frame}.sort_values(by={keys!r}, ascending={asc!r}, kind="mergesort").reset_index(drop=True)'],
                imps,
                params_used,
                [],
                True,
                dict(in_kinds),
            )

        if kind == "Summarize":
            s_fields = cfg.get("summarize_fields", [])
            if not s_fields:
                raise UnsupportedLowering("Summarize requires fields")
            group_fields = [f for f in s_fields if f["action"] == "GroupBy"]
            measures = [f for f in s_fields if f["action"] != "GroupBy"]
            groups = [f["field"] for f in group_fields]
            out_cols = [f.get("rename") or f["field"] for f in [*group_fields, *measures]]

            agg_map = {
                "Sum": "sum",
                "Count": "size",
                "Min": "min",
                "Max": "max",
                "Avg": "mean",
                "Median": "median",
            }
            simple_groups = (
                bool(groups)
                and all(not f.get("rename") or f["rename"] == f["field"] for f in group_fields)
                and len(set(out_cols)) == len(out_cols)
                and all(m["action"] in agg_map for m in measures)
                and set(out_cols[len(groups) :]).isdisjoint({"self", "func", "engine", "engine_kwargs"})
            )
            if simple_groups:
                lines = [
                    f"if {frame}.empty:",
                    f"    return pd.DataFrame(columns={out_cols!r})",
                ]
                num_cols = sorted({m["field"] for m in measures if m["action"] in {"Sum", "Avg", "Median"}})
                work = frame
                if num_cols:
                    lines.append(f"work = {frame}.copy()")
                    for nc in num_cols:
                        lines.append(f'work[{nc!r}] = pd.to_numeric(work[{nc!r}], errors="coerce")')
                    work = "work"
                if measures:
                    named_aggs = ", ".join(
                        f"{(m.get('rename') or m['field'])!r}: ({m['field']!r}, {agg_map[m['action']]!r})"
                        for m in measures
                    )
                    lines.append(f"grouped = {work}.groupby({groups!r}, sort=False, dropna=False)")
                    lines.append(f"return grouped.agg(**{{{named_aggs}}}).reset_index()")
                else:
                    lines.append(f"return {work}[{groups!r}].drop_duplicates().reset_index(drop=True)")
                return lines, imps, params_used, [], False, {}

            # General Summarize fallback (handles Concat, Mode, CountBlank, ungrouped reductions, etc.)
            from alteryx2python.generator.native_tabular import lower_tabular

            dummy_compiler = type("_C", (), {"linker": self.linker})()
            body = lower_tabular(dummy_compiler, "Summarize", cfg, frame)
            return body, imps, params_used, [], False, {}

        if kind == "Unique":
            u_fields = cfg.get("unique_fields")
            subset = repr(u_fields) if u_fields else f"list({frame}.columns)"
            lines = [
                f"keys = {subset}",
                f'ordered = {frame}.sort_values(keys, kind="stable", na_position="first")',
            ]
            lines.append('duplicate = ordered.duplicated(subset=keys, keep="first")')
            want_u = "Unique" in consumed_anchors or not consumed_anchors
            want_d = "Duplicates" in consumed_anchors
            if want_u and not want_d:
                lines.append("return ordered.loc[~duplicate].copy()")
                return lines, imps, params_used, [], True, dict(in_kinds)
            if want_d and not want_u:
                lines.append("return ordered.loc[duplicate].copy()")
                return lines, imps, params_used, [], True, dict(in_kinds)
            lines.append("return ordered.loc[~duplicate].copy(), ordered.loc[duplicate].copy()")
            return lines, imps, params_used, [], False, dict(in_kinds)

        if kind == "RecordID":
            from alteryx2python.tools.recordid import TYPE_MAP

            f_name = cfg.get("field_name", "RecordID")
            start = int(cfg.get("start_value", 1))
            pos = int(cfg.get("position", 0))
            dtype = cfg.get("field_type", "Int32")
            groups = cfg.get("group_fields", [])
            if dtype not in TYPE_MAP or pos not in (0, 1):
                raise UnsupportedLowering("Unsupported RecordID type/position")
            lines = [f"out = {frame}.copy()"]
            if groups:
                lines.append(f'out = out.sort_values({groups!r}, kind="stable", na_position="first").reset_index(drop=True)')
                lines.append(f"out[{f_name!r}] = (out.groupby({groups!r}, sort=False, dropna=False).cumcount() + {start}).astype({dtype!r})")
            else:
                lines.append(f"out[{f_name!r}] = pd.Series(range({start}, {start} + len(out)), index=out.index, dtype={dtype!r})")
            if pos == 0:
                lines.append(f"out = out[[{f_name!r}] + [c for c in out.columns if c != {f_name!r}]]")
            lines.append("return out")
            out_k = {**in_kinds, f_name: "numeric"}
            return lines, imps, params_used, [], True, out_k

        if kind == "Sample":
            from alteryx2python.generator.native_tabular import lower_tabular

            dummy_compiler = type("_C", (), {"linker": self.linker})()
            body = lower_tabular(dummy_compiler, "Sample", cfg, frame)
            return body, imps, params_used, [], True, dict(in_kinds)

        if kind == "Union":
            from alteryx2python.tools.union import _expected_output_columns, _ordered_input_anchors

            ordered = _ordered_input_anchors(arg_names, cfg)
            if not ordered:
                raise UnsupportedLowering("Union needs input data")
            frames_expr = "[" + ", ".join(arg_names[a] for a in ordered) + "]"
            mode = str(cfg.get("mode", "ByName")).lower()
            lines = [f"frames = {frames_expr}"]
            if mode == "byname":
                lines.extend([
                    "columns = list(dict.fromkeys(col for f in frames for col in f.columns))",
                    "aligned = [f.reindex(columns=columns) for f in frames]",
                ])
            elif mode == "bypos":
                expected = _expected_output_columns(cfg.get("expected_output_schema"))
                lines.extend([
                    f"columns = {expected!r}" if expected else "columns = list(frames[0].columns)",
                    "aligned = [f.set_axis(columns[:len(f.columns)], axis=1).reindex(columns=columns) for f in frames]",
                ])
            else:
                raise UnsupportedLowering(f"Unsupported Union mode: {mode}")
            lines.append("return pd.concat(aligned, ignore_index=True)")
            return lines, imps, params_used, [], False, {}

        if kind == "Join":
            from alteryx2python.tools.join import join_frames, join_keys

            left_arg, right_arg = arg_names["Left"], arg_names["Right"]
            by_pos = bool(cfg.get("join_by_record_pos", False))
            l_keys = [] if by_pos else join_keys(cfg, "Left")
            r_keys = [] if by_pos else join_keys(cfg, "Right")
            if not by_pos and (not l_keys or len(l_keys) != len(r_keys)):
                raise UnsupportedLowering("Join requires equally many Left and Right fields")

            sel_fields = cfg.get("select_fields", [])
            h_join = self.linker.function(join_frames)
            lines = [
                f"joined_out, left_out, right_out = {h_join}({left_arg}, {right_arg}, {l_keys!r}, {r_keys!r}, {sel_fields!r}, {cfg.get('order_changed', True)!r}, {by_pos!r})"
            ]
            if consumed_anchors == {"Join"}:
                lines.append("return joined_out")
            elif consumed_anchors == {"Left"}:
                lines.append("return left_out")
            elif consumed_anchors == {"Right"}:
                lines.append("return right_out")
            else:
                ret_items = []
                for anch, var_n in (("Left", "left_out"), ("Join", "joined_out"), ("Right", "right_out")):
                    if anch in consumed_anchors or not consumed_anchors:
                        ret_items.append(var_n)
                lines.append("return " + ", ".join(ret_items))
            return lines, imps, params_used, [], False, {}

        if kind == "AppendFields":
            from alteryx2python.tools.appendfields import append_rows

            t_arg, s_arg = arg_names["Targets"], arg_names["Source"]
            lines = []
            if cfg.get("cartesian_mode", "Error") == "Error":
                lines.extend([
                    f"if len({t_arg}) * len({s_arg}) > max(len({t_arg}), len({s_arg})):",
                    '    raise ValueError("AppendFields CartesianMode=Error rejects many-to-many append")',
                ])
            sel = [{k: f[k] for k in ("source", "selected", "rename") if k in f} for f in cfg.get("select_fields", [])]
            h_app = self.linker.function(append_rows)
            lines.append(f"out, col_names = {h_app}({t_arg}, {s_arg}, {sel!r}, {bool(cfg.get('order_changed'))!r})")
            for f in cfg.get("select_fields", []):
                ref, dtype = f["source"], f.get("dtype")
                if dtype and f.get("selected", True) and ref != "*Unknown":
                    cast_c, _ = self._native_cast_expr("out[col_name]", dtype, f.get("size"))
                    lines.extend([
                        f"if {ref!r} in col_names:",
                        f"    col_name = col_names[{ref!r}]",
                        f"    out[col_name] = {cast_c}",
                    ])
            lines.append("return out")
            return lines, imps, params_used, [], False, {}

        if kind in {"RunningTotal", "Rank", "TextToColumns"}:
            from alteryx2python.generator.native_tabular import lower_tabular

            dummy_compiler = type("_C", (), {"linker": self.linker})()
            body = lower_tabular(dummy_compiler, kind, cfg, frame)
            return body, imps, params_used, [], False, {}

        if kind in {"Transpose", "AutoField", "RegEx", "CrossTab"}:
            from alteryx2python.generator.native_reshape import lower_reshape

            dummy_compiler = type("_C", (), {"linker": self.linker})()
            body = lower_reshape(dummy_compiler, kind, cfg, frame)
            return body, imps, params_used, [], False, {}

        if kind == "BlockUntilDone":
            count = len([a for a in outputs if a in consumed_anchors]) or len(outputs)
            copies = ", ".join(f"{frame}.copy()" for _ in range(count))
            return [f"return {copies}"], imps, params_used, [], False, dict(in_kinds)

        if kind in {"WaitASecond", "WaitSeconds"}:
            secs = float(cfg.get("seconds", 1))
            imps.add("import time")
            return [f"time.sleep({secs!r})", f"return {frame}.copy()"], imps, params_used, [], False, dict(in_kinds)

        if kind in {"MacroInput", "MacroBoundaryInput", "MacroOutput"}:
            return ([f"return {frame}.copy()"] if arg_names else ["return pd.DataFrame()"]), imps, params_used, [], bool(arg_names), dict(in_kinds)

        if kind == "DateTimeNow":
            from alteryx2python.tools.datetimenow import FORMAT_MAP, date_time_frame

            out_fmt = cfg.get("output_format", "yyyy-MM-dd")
            if out_fmt not in FORMAT_MAP:
                raise UnsupportedLowering(f"DateTimeNow output format is not supported: {out_fmt}")
            h_dt = self.linker.function(date_time_frame)
            as_of_var = param_names.get("__as_of__", "None")
            if "__as_of__" in param_names:
                params_used.add(as_of_var)
            return [f"return {h_dt}({as_of_var} or {cfg.get('now')!r}, {out_fmt!r})"], imps, params_used, [], False, {}

        if kind in {"Directory", "DynamicInput", "RunCommand"}:
            if self.is_macro:
                raise UnsupportedLowering(f"{kind} #{node.node_id} needs an external operation binding in a reusable macro")
            if kind == "Directory":
                key = f"directory_{node.node_id}"
                call_args = ""
            elif kind == "DynamicInput":
                key = f"dynamic_input_{node.node_id}"
                call_args = f"{frame}, {cfg['read_list_field']!r}"
            else:
                self.needs_commands = True
                key = f"command_{node.node_id}"
                args = [frame if arg_names else "None"]
                for binding in self.opt.parameter_bindings:
                    if binding.get("kind") == "command" and str(binding["node_id"]) == node.node_id:
                        parameter = param_names[binding["name"]]
                        params_used.add(parameter)
                        args.append(f"{binding['path'][0]}={parameter}")
                call_args = ", ".join(args)
            return [f"return operations[{key!r}]({call_args})"], imps, params_used, ["operations"], False, {}

        if kind in {"PortfolioComposerTable", "PortfolioComposerText", "PortfolioComposerLayout"}:
            from alteryx2python.tools import delivery as delivery_tools

            if self.delivery_profile == delivery_tools.XLSX_PROFILE:
                if kind == "PortfolioComposerLayout":
                    groups, flds, sec = delivery_tools.xlsx_layout_options(cfg)
                    h_fn = self.linker.function(delivery_tools.xlsx_report_layout)
                    return [f"return {h_fn}({frame}, {groups!r}, {flds!r}, {sec!r})"], imps, params_used, [], False, {}
                if kind == "PortfolioComposerTable":
                    if cfg.get("table_mode", "Basic") != "Basic" or cfg.get("show_bar_graph"):
                        raise UnsupportedLowering("XLSX profile requires a Basic reporting table")
                    h_fn = self.linker.function(delivery_tools.xlsx_report_table)
                    return (
                        [f"return {h_fn}({frame}, {cfg.get('table_fields', [])!r}, {cfg.get('grouping_fields', [])!r}, {cfg.get('show_header') is not False!r})"],
                        imps,
                        params_used,
                        [],
                        False,
                        {},
                    )
                raise UnsupportedLowering(f"XLSX table profile does not support {kind}")
            if self.delivery_profile not in {delivery_tools.PROFILE, delivery_tools.SMTP_PROFILE}:
                raise UnsupportedLowering(f"{kind} requires explicit html-draft-v1 or html-smtp-v1 profile")
            if kind == "PortfolioComposerTable":
                if cfg.get("grouping_fields") or cfg.get("table_mode", "Basic") != "Basic" or cfg.get("show_bar_graph"):
                    raise UnsupportedLowering("Only an ungrouped Basic HTML table is supported")
                h_fn = self.linker.function(delivery_tools.report_table)
                return [f"return {h_fn}({frame}, {cfg.get('table_fields', [])!r}, {cfg.get('show_header') is not False!r})"], imps, params_used, [], False, {}
            if kind == "PortfolioComposerText":
                if cfg.get("raw_mode") or cfg.get("rich_text_mode") or cfg.get("header_mode"):
                    raise UnsupportedLowering("Rich/dynamic report text needs a verified template")
                h_fn = self.linker.function(delivery_tools.report_text)
                return [f"return {h_fn}({cfg.get('message', '')!r}, {cfg.get('output_field', 'Report')!r})"], imps, params_used, [], False, {}
            if kind == "PortfolioComposerLayout":
                if cfg.get("grouping_fields") or cfg.get("orientation", "").lower() not in {"", "vertical"}:
                    raise UnsupportedLowering("Only ungrouped vertical HTML layout is supported")
                h_fn = self.linker.function(delivery_tools.report_layout)
                return [f"return {h_fn}({frame}, {cfg.get('layout_fields', [])!r})"], imps, params_used, [], False, {}

        if kind in {"GenerateRows", "MultiFieldFormula", "MultiRowFormula", "Message", "ControlContainer"}:
            return self._lower_special_stateful(node, cfg, arg_names, outputs, param_names, static_consts)

        if kind == "JupyterCode":
            from alteryx2python.generator.python_tool import lower_python_script, saved_python_script

            body, py_outputs = lower_python_script(saved_python_script(cfg), arg_names, static_consts, self.linker)
            del py_outputs
            return body, imps, params_used, [], False, {}

        if kind == "MacroSubgraphCall":
            m_key = node.metadata["reusable_macro_key"]
            m_spec = self.opt.reusable_macros[m_key]
            fn_name = f"run_{m_key}"
            imps.add(f"from .macros.{m_key} import {fn_name}")
            ordered_args = [arg_names.get(a) or next(iter(arg_names.values())) for a in m_spec.input_anchors] if arg_names else []
            caller_ans = node.metadata.get("macro_call_answers", {})
            kw_parts: list[str] = []
            for p_entry in m_spec.parameters:
                p_orig = p_entry["name"]
                p_py = _ident(p_entry.get("python_name") or p_orig, "param")
                val = caller_ans.get(p_orig, p_entry.get("default"))
                kw_parts.append(f"{p_py}={val!r}")
            all_args = ", ".join([*ordered_args, *kw_parts])
            return [f"return {fn_name}({all_args})"], imps, params_used, [], False, {}

        if kind == "MacroLoopCall":
            m_key = node.metadata["loop_macro_key"]
            m_spec = self.opt.loop_macros[m_key]
            fn_name = f"run_{m_key}_{m_spec.kind}"
            imps.add(f"from .macros.{m_key} import {fn_name}")
            if m_spec.kind == "batch":
                ctrl_anchor = m_spec.control_anchor or ("Control" if "Control" in arg_names else m_spec.control_param or "Control")
                ctrl_arg = arg_names.get(ctrl_anchor) or next(iter(arg_names.values()))
                data_args = [v for k, v in arg_names.items() if k != ctrl_anchor]
                caller_ans = dict(node.metadata.get("macro_call_answers", {}))
                ctrl_field = None
                for line in str(caller_ans.get("ControlParams", "")).splitlines():
                    k, sep, f_n = line.partition("=")
                    if sep and k.strip() == m_spec.control_param:
                        ctrl_field = f_n.strip()
                call_parts = [ctrl_arg, *data_args, f"control_field={ctrl_field!r}"]
                return [f"return {fn_name}({', '.join(call_parts)})"], imps, params_used, [], False, {}
            else:
                ordered_args = [arg_names.get(a) or next(iter(arg_names.values())) for a in m_spec.input_anchors] if arg_names else []
                return [f"return {fn_name}({', '.join(ordered_args)})"], imps, params_used, [], False, {}

        return None

    def _lower_special_stateful(
        self,
        node: NodeIR,
        cfg: dict[str, Any],
        arg_names: dict[str, str],
        outputs: tuple[str, ...],
        param_names: dict[str, str],
        static_consts: dict[str, Any],
    ) -> tuple[list[str], set[str], set[str], list[str], bool, dict[str, str]]:
        kind = node.tool_type
        frame = next(iter(arg_names.values()), None)
        imps: set[str] = set()
        params_used: set[str] = set()

        if kind == "ControlContainer":
            if not outputs:
                return ["return None"], imps, params_used, [], False, {}
            from alteryx2python.tools.canvas import control_log_frame

            active = "False" if cfg.get("disabled") else (f"len({arg_names['Control']}.index) > 0" if "Control" in arg_names else "True")
            if node.metadata.get("disabled_parameter") and node.metadata["disabled_parameter"] in param_names:
                p_py = param_names[node.metadata["disabled_parameter"]]
                params_used.add(p_py)
                active = f"(not {p_py}) and ({active})"
            h_log = self.linker.function(control_log_frame)
            return [f"return {h_log}({node.node_id!r}, {active})"], imps, params_used, [], False, {}

        if kind == "Message":
            self.has_messages = True
            when = (cfg.get("when") or "First").lower()
            severity = (cfg.get("type") or "Message").lower()
            if frame is None or when not in {"first", "last", "filter", "all"} or severity not in {"message", "warning", "error", "errorstop"}:
                raise UnsupportedLowering(f"Unsupported Message configuration: {when}/{severity}")
            parsed_msg = parse_expression(cfg["message_expression"])
            params_used |= self._collect_expr_params(parsed_msg, param_names)
            msg_code = self._scalar_expression(parsed_msg, param_names, static_consts)
            if severity in {"error", "errorstop"}:
                emit = f"raise ValueError(str({msg_code}))"
            elif severity == "warning":
                imps.add("import warnings")
                emit = f"warnings.warn(str({msg_code}), RuntimeWarning)"
            else:
                imps.add("import logging")
                emit = f'logging.getLogger("workflow.message").info(str({msg_code}))'
            if when == "all":
                return ["row = {}", emit, f"return {frame}.copy()"], imps, params_used, [], False, {}
            if when == "filter":
                parsed_flt = parse_expression(cfg["filter"])
                params_used |= self._collect_expr_params(parsed_flt, param_names)
                flt_code = self._scalar_expression(parsed_flt, param_names, static_consts)
                rows_iter = f"(row for row in {frame}.to_dict('records') if {flt_code})"
            else:
                take = "head" if when == "first" else "tail"
                rows_iter = f"({frame}.{take}(1).to_dict('records') or [{{}}])"
            return [f"for row in {rows_iter}:", f"    {emit}", f"return {frame}.copy()"], imps, params_used, [], False, {}

        if kind == "GenerateRows":
            from alteryx2python.tools.generaterows import _strip_comments

            t_field = cfg.get("update_field_name") if cfg.get("update_field") else cfg.get("create_field_name")
            if not t_field:
                raise UnsupportedLowering("GenerateRows needs a target field")
            exprs = []
            for key in ("expression_init", "expression_cond", "expression_loop"):
                p_ast = parse_expression(_strip_comments(cfg[key]))
                params_used |= self._collect_expr_params(p_ast, param_names)
                exprs.append(self._scalar_expression(p_ast, param_names, static_consts))
            init_c, cond_c, loop_c = exprs
            return (
                [
                    f"seeds = {frame}.to_dict('records')" if frame else "seeds = [{}]",
                    "rows = []",
                    "for seed in seeds:",
                    "    row = dict(seed)",
                    f"    row[{t_field!r}] = {init_c}",
                    f"    while bool({cond_c}):",
                    "        rows.append(dict(row))",
                    "        if len(rows) > 100000:",
                    '            raise RuntimeError("GenerateRows exceeded safety limit of 100000 rows")',
                    f"        row[{t_field!r}] = {loop_c}",
                    "return pd.DataFrame(rows)",
                ],
                imps,
                params_used,
                [],
                False,
                {},
            )

        if kind == "MultiFieldFormula":
            p_ast = parse_expression(cfg["expression"])
            params_used |= self._collect_expr_params(p_ast, param_names)
            expr_c = self._scalar_expression(p_ast, param_names, static_consts)
            flds = [str(f) for f in cfg.get("fields", [])]
            explicit = [f for f in flds if f != "*Unknown"]
            lines = [f"out = {frame}.copy()", f"fields = [f for f in {explicit!r} if f in {frame}.columns]"]
            if "*Unknown" in flds:
                lines.append(f"fields.extend(c for c in {frame}.columns if c not in fields)")
            addon = str(cfg.get("new_field_add_on", ""))
            target = (
                "field"
                if not cfg.get("copy_output")
                else (f"{addon!r} + field" if str(cfg.get("new_field_add_on_pos", "Suffix")).lower() == "prefix" else f"field + {addon!r}")
            )
            lines.extend([
                f"for field in (fields or list({frame}.columns)):",
                f"    out_col = {target}",
                "    vals = []",
                "    for row in out.to_dict('records'):",
                '        row["_CurrentField_"] = row[field]',
                f"        vals.append({expr_c})",
                "    out[out_col] = vals",
                "return out",
            ])
            return lines, imps, params_used, [], False, {}

        if kind == "MultiRowFormula":
            from dataclasses import fields as dc_fields, is_dataclass
            from alteryx2python.expressions.ast import FieldReference
            from alteryx2python.tools.multirowformula import _empty_value_for, _target_field

            target = _target_field(cfg)
            p_ast = parse_expression(cfg["expression"])
            params_used |= self._collect_expr_params(p_ast, param_names)
            expr_c = self._scalar_expression(p_ast, param_names, static_consts)
            groups, dtype = cfg.get("group_by_fields", []), cfg.get("create_field_type", "")
            refs: dict[str, tuple[int, str]] = {}

            def collect_refs(v) -> None:
                if isinstance(v, FieldReference):
                    m = re.fullmatch(r"Row(-?\d+):(.+)", v.name)
                    if m and 0 < abs(int(m[1])) <= int(cfg.get("num_rows", 1)):
                        refs[v.name] = (int(m[1]), m[2])
                elif is_dataclass(v):
                    for f in dc_fields(v):
                        collect_refs(getattr(v, f.name))
                elif isinstance(v, list):
                    for item in v:
                        collect_refs(item)

            collect_refs(p_ast)
            g_key = f"tuple(row.get(f) for f in {groups!r})" if groups else "()"
            r_key = f"tuple(rec.get(f) for f in {groups!r})" if groups else "()"
            lines = [f"rows = {frame}.copy().to_dict('records')"]
            if not cfg.get("update_field"):
                lines.extend(["for row in rows:", f"    row[{target!r}] = {_empty_value_for(target, target, dtype)!r}"])
            lines.extend([
                "pos_by_group = {}",
                "for idx, row in enumerate(rows):",
                f"    pos_by_group.setdefault({g_key}, []).append(idx)",
                "for idx, rec in enumerate(rows):",
                "    row = dict(rec)",
                f"    positions = pos_by_group[{r_key}]",
                "    pos = positions.index(idx)",
            ])
            for ref_name, (offset, fld) in refs.items():
                fb = "(positions[0] if rel < 0 else positions[-1])" if str(cfg.get("other_rows", "Empty")).lower() == "nearest" else "None"
                lines.extend([
                    f"    rel = pos + {offset}",
                    f"    nbr = positions[rel] if 0 <= rel < len(positions) else {fb}",
                    f"    row[{ref_name!r}] = {_empty_value_for(fld, target, dtype)!r} if nbr is None else rows[nbr].get({fld!r})",
                ])
            conv = (
                "bool" if dtype.lower() == "bool" else (
                    "int" if dtype.lower() in {"byte", "int16", "int32", "int64"} else (
                        "float" if dtype.lower() in {"fixeddecimal", "double", "float"} else None
                    )
                )
            )
            comp = f"val if val is None or pd.isna(val) else {conv}(val)" if conv else "val"
            lines.extend([
                "    try:",
                f"        val = {expr_c}",
                "    except TypeError:",
                "        val = None",
                f"    rec[{target!r}] = {comp}",
                "return pd.DataFrame(rows)",
            ])
            return lines, imps, params_used, [], False, {}

        raise UnsupportedLowering(f"Unhandled stateful tool: {kind}")

    def _lower_via_registry_template(
        self,
        node: NodeIR,
        cfg: dict[str, Any],
        arg_names: dict[str, str],
        outputs: tuple[str, ...],
    ) -> list[str]:
        """Fallback AST specialization for other audited tools (DataCleansing, FindReplace, JSONParse, etc.)."""
        from alteryx2python.generator.readable import _ReturnFrames, _Specialize
        from alteryx2python.tools.registry import TOOL_REGISTRY

        meta = TOOL_REGISTRY.get(node.tool_type)
        if meta is None or meta.execution_profile == "unavailable":
            raise UnsupportedLowering(f"No executable native template for {node.tool_type}")
        fn = inspect.unwrap(meta.function)
        if fn.__module__.endswith((".baseline", ".unavailable", ".reporting")):
            raise UnsupportedLowering(f"Metadata/passthrough implementation is not an executable template: {node.tool_type}")
        src = textwrap.dedent(inspect.getsource(fn))
        tree = strip_annotations(ast.parse(src).body[0])
        tree.name, tree.decorator_list = "_stage_impl", []
        tree.args = ast.arguments(
            posonlyargs=[],
            args=[ast.arg(v) for v in arg_names.values()],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
            vararg=None,
            kwarg=None,
        )
        tree = RemoveTracing().visit(tree)
        tree = _Specialize(cfg, arg_names, {}).visit(tree)
        tree = _ReturnFrames(outputs).visit(tree)
        tree = simplify_template(tree)
        import warnings

        ns = {**fn.__globals__, **inspect.getclosurevars(fn).nonlocals, "warnings": warnings}
        tree = self.linker.bind_globals(tree, ns)
        tree = simplify_template(tree)
        return [ast.unparse(ast.fix_missing_locations(stmt)) for stmt in tree.body]

    def _describe_node_audit(self, node: NodeIR, cfg: dict[str, Any]) -> tuple[str, str]:
        """Synthesize deterministic (tool_label, summary) metadata for step-by-step auditing."""
        tool_id = str(node.source_tool_id or node.node_id)
        label = f"{node.tool_type} #{tool_id}"
        kind = node.tool_type

        if kind == "Select":
            explicit = [f for f in cfg.get("select_fields", []) if f.get("selected", True) and f.get("source") != "*Unknown"]
            names = [str(f.get("rename") or f["source"]) for f in explicit]
            casts = [f"{f.get('rename') or f['source']}:{f['dtype']}" for f in explicit if f.get("dtype")]
            col_part = f"[{', '.join(names[:5])}{', ...' if len(names) > 5 else ''}]" if names else "all columns"
            cast_part = f"; cast [{', '.join(casts[:4])}{', ...' if len(casts) > 4 else ''}]" if casts else ""
            return label, f"Select {col_part}{cast_part}"

        if kind == "Formula":
            computed = [str(f["field"]) for f in cfg.get("formula_fields", []) if f.get("enabled", True)]
            col_part = f"[{', '.join(computed[:5])}{', ...' if len(computed) > 5 else ''}]"
            return label, f"Compute {col_part}"

        if kind == "Filter":
            return label, "Filter rows"

        if kind == "Summarize":
            fields = cfg.get("fields", [])
            groups = [str(f["field"]) for f in fields if f.get("action") == "GroupBy"]
            aggs = [f"{f.get('action')}({f.get('field')})" for f in fields if f.get("action") != "GroupBy"]
            grp_part = f" by [{', '.join(groups[:4])}]" if groups else ""
            agg_part = f" -> [{', '.join(aggs[:4])}{', ...' if len(aggs) > 4 else ''}]" if aggs else ""
            return label, f"Summarize{grp_part}{agg_part}"

        if kind == "Join":
            if cfg.get("join_by_record_pos"):
                return label, "Join streams by record position"
            from alteryx2python.tools.join import join_keys

            l_k = join_keys(cfg, "Left")
            r_k = join_keys(cfg, "Right")
            return label, f"Join Left={l_k} with Right={r_k}"

        if kind == "Union":
            return label, f"Union streams ({cfg.get('mode', 'ByName')})"

        if kind == "Sort":
            keys = [f"{f.get('field')} {str(f.get('order', 'Asc'))[:4]}" for f in cfg.get("fields", [])]
            return label, f"Sort by [{', '.join(keys[:4])}]"

        if kind == "Unique":
            return label, f"Deduplicate on {cfg.get('unique_fields', [])}"

        if kind == "RecordID":
            grp = f" grouped by {cfg['group_fields']}" if cfg.get("group_fields") else ""
            return label, f"Assign {cfg.get('field_name', 'RecordID')} from {cfg.get('start_value', 1)}{grp}"

        if kind == "Sample":
            return label, f"Sample {cfg.get('mode', 'First')} N={cfg.get('n', '')}"

        if kind == "CrossTab":
            return label, f"CrossTab header={cfg.get('header_field')} value={cfg.get('data_field')}"

        if kind == "Transpose":
            return label, f"Transpose keys={cfg.get('key_fields', [])} data={cfg.get('data_fields', [])[:4]}"

        if kind == "RegEx":
            return label, f"RegEx {cfg.get('method', '')} on [{cfg.get('field', '')}]"

        if kind == "TextToColumns":
            return label, f"Split [{cfg.get('field', '')}] to columns"

        if kind == "AppendFields":
            return label, "Append source fields onto target rows"

        if kind == "MacroSubgraphCall":
            return label, f"Invoke reusable macro {node.metadata.get('reusable_macro_key', '')}"

        if kind == "MacroLoopCall":
            return label, f"Execute loop macro {node.metadata.get('loop_macro_key', '')}"

        ann = _annotation_name(node)
        return label, ann if ann else f"Execute {kind}"

    def compile_pipeline(self) -> tuple[str, list[dict[str, Any]]]:
        """Return (pipeline_py_source, node_mapping_entries)."""
        from alteryx2python.runtime.executor import (
            _edge_connection_name,
            _next_input_anchor_name,
            _normalized_config,
            _topological_order,
        )
        from alteryx2python.runtime.scheduling import container_guards
        from alteryx2python.tools.registry import TOOL_REGISTRY

        by_id = {n.node_id: n for n in self.workflow.nodes}
        order = _topological_order(self.workflow.nodes, self.workflow.edges)

        # Determine which output anchors of each node are actually consumed downstream
        consumed_by_node: dict[str, set[str]] = {n.node_id: set() for n in self.workflow.nodes}
        consumers_count: dict[tuple[str, str], int] = {}
        for edge in self.workflow.edges:
            consumed_by_node.setdefault(edge.source_node_id, set()).add(edge.source_anchor)
            consumers_count[(edge.source_node_id, edge.source_anchor)] = (
                consumers_count.get((edge.source_node_id, edge.source_anchor), 0) + 1
            )

        param_names = self.config_spec.python_param_names
        static_consts = {
            k: v
            for k, v in (self.workflow.metadata.get("workflow_constants") or {}).items()
            if k not in param_names
        }

        used_func_names = {"run_pipeline", "transform", "_transform", "_run_step"}
        used_var_names: set[str] = {"audit", "config", "params", "results", "read_table", "write_result", "operations"} | set(param_names.values())
        var_by_anchor: dict[tuple[str, str], str] = {}
        orchestration_lines: list[str] = []
        mapping_entries: list[dict[str, Any]] = []
        compiled_ops: dict[str, _CompiledOp] = {}

        def alloc_var(stem: str) -> str:
            base = _ident(stem, "df")
            cand, idx = base, 1
            while cand in used_var_names:
                idx += 1
                cand = f"{base}_{idx}"
            used_var_names.add(cand)
            return cand

        def alloc_func(stem: str) -> str:
            base = _ident(stem, "transform")
            cand, idx = base, 1
            while cand in used_func_names:
                idx += 1
                cand = f"{base}_{idx}"
            used_func_names.add(cand)
            return cand

        # Track whether pipeline needs io_utils imports
        used_io_helpers: set[str] = set()
        sink_keys: list[str] = []

        for node_id in order:
            node = by_id[node_id]
            cfg = deepcopy(_normalized_config(node))
            cfg.update(
                node_id=node_id,
                source_tool_id=node.source_tool_id,
                expected_output_schema=node.expected_output_schema,
            )

            # Handle I/O & Reference Boundary Nodes directly in run_pipeline(config)
            if node.tool_type == "DbFileInput":
                in_key = self.config_spec.input_key_by_node[node_id]
                var_name = alloc_var(f"{in_key}_df")
                var_by_anchor[(node_id, "Output")] = var_name
                used_io_helpers.add("read_input_table")
                tool_lbl = f"DbFileInput #{node.source_tool_id or node_id}"
                if self.is_macro:
                    orchestration_lines.append(f"    {var_name} = read_input_table(config, {in_key!r})")
                else:
                    orchestration_lines.append(f"    {var_name} = read_table('inputs', {in_key!r}, {tool_lbl!r})")
                mapping_entries.append({
                    "node_id": node_id,
                    "source_tool_id": node.source_tool_id,
                    "tool_type": node.tool_type,
                    "function": "run_pipeline",
                    "outputs": ["Output"],
                    "variables": {"Output": var_name},
                })
                continue

            if node.tool_type == "TextInput":
                ref_key = self.config_spec.reference_key_by_node[node_id]
                var_name = alloc_var(f"{ref_key}_df")
                var_by_anchor[(node_id, "Output")] = var_name
                used_io_helpers.add("read_reference_table")
                tool_lbl = f"TextInput #{node.source_tool_id or node_id}"
                if self.is_macro:
                    orchestration_lines.append(f"    {var_name} = read_reference_table(config, {ref_key!r})")
                else:
                    orchestration_lines.append(f"    {var_name} = read_table('references', {ref_key!r}, {tool_lbl!r})")
                ref_dtypes = self.config_spec.references[ref_key].get("dtypes", {})
                self.column_kinds_by_var[var_name] = {
                    col: ("numeric" if dt in {"int64", "Int64", "float64"} else ("bool" if dt in {"bool", "boolean"} else "string" if dt == "string" else "any"))
                    for col, dt in ref_dtypes.items()
                }
                mapping_entries.append({
                    "node_id": node_id,
                    "source_tool_id": node.source_tool_id,
                    "tool_type": node.tool_type,
                    "function": "run_pipeline",
                    "outputs": ["Output"],
                    "variables": {"Output": var_name},
                })
                continue

            if node.tool_type in {"DbFileOutput", "PortfolioComposerRender", "Email"}:
                out_key = self.config_spec.output_key_by_node[node_id]
                in_edges = [e for e in self.workflow.edges if e.target_node_id == node_id]
                if not in_edges:
                    raise UnsupportedLowering(f"{node.tool_type} #{node_id} requires an input connection")
                src_var = var_by_anchor[(in_edges[0].source_node_id, in_edges[0].source_anchor)]
                used_io_helpers.add("write_output_table")
                out_fmt = self.config_spec.outputs[out_key].get("format", "")
                if out_fmt == "render_html":
                    self.needs_render_html = True
                elif out_fmt == "render_xlsx":
                    self.needs_render_xlsx = True
                elif out_fmt.startswith("email"):
                    self.needs_email = True

                guards = self._build_guards(node, by_id, var_by_anchor, param_names, container_guards)
                if "False" not in guards:
                    sink_keys.append(out_key)
                tool_lbl = f"{node.tool_type} #{node.source_tool_id or node_id}"
                write_lines = (
                    [f"written_outputs[{out_key!r}] = write_output_table({src_var}, config, {out_key!r})"]
                    if self.is_macro else [
                        f"results[{out_key!r}] = {src_var}",
                        "if write_result is not None:",
                        f"    write_result({src_var}, {out_key!r}, {tool_lbl!r})",
                    ]
                )
                if guards:
                    orchestration_lines.append(f"    if {' and '.join(guards)}:")
                    orchestration_lines.extend("        " + line for line in write_lines)
                    if not self.is_macro:
                        orchestration_lines.append("    elif audit is not None:")
                        orchestration_lines.append(f"        audit.skip_step({out_key!r}, {tool_lbl!r}, {f'Write output {out_key}'!r})")
                else:
                    orchestration_lines.extend("    " + line for line in write_lines)
                mapping_entries.append({
                    "node_id": node_id,
                    "source_tool_id": node.source_tool_id,
                    "tool_type": node.tool_type,
                    "function": "run_pipeline",
                    "outputs": [],
                    "variables": {},
                })
                continue

            # Pure / Stage Transformation Node
            arg_names: dict[str, str] = {}
            input_vars: dict[str, str] = {}
            conn_names: dict[str, str] = {}
            for edge in self.workflow.edges:
                if edge.target_node_id != node_id:
                    continue
                anchor = _next_input_anchor_name(arg_names, edge.target_anchor)
                arg_names[anchor] = "df" if len(arg_names) == 0 and edge.target_anchor == "Input" else f"{_ident(anchor)}_df"
                input_vars[anchor] = var_by_anchor[(edge.source_node_id, edge.source_anchor)]
                c_name = _edge_connection_name(edge)
                if c_name:
                    conn_names[anchor] = c_name
            if len(arg_names) > 1 and "Input" in arg_names and arg_names["Input"] == "df":
                arg_names["Input"] = "input_df"
            if conn_names:
                cfg["input_connection_names"] = conn_names

            meta = TOOL_REGISTRY.get(node.tool_type) if node.tool_type not in {
                "MacroSubgraphCall", "MacroLoopCall", "MacroInput", "MacroBoundaryInput", "MacroOutput"
            } else None
            if node.tool_type in {"MacroSubgraphCall", "MacroLoopCall", "ControlContainer", "DateTimeNow"}:
                all_outputs = tuple(a.name for a in node.output_anchors)
            elif node.tool_type in {"MacroInput", "MacroBoundaryInput", "MacroOutput"}:
                all_outputs = ("Output",)
            else:
                all_outputs = meta.output_anchors if meta is not None else ("Output",)

            consumed = consumed_by_node.get(node_id, set())
            # For Filter / Unique / Join / BlockUntilDone, only return anchors actually consumed (unless terminal!)
            if consumed and node.tool_type in {"Filter", "Unique", "Join", "BlockUntilDone"}:
                eff_outputs = tuple(a for a in all_outputs if a in consumed)
            elif not consumed and node.tool_type in {"Filter", "Unique"}:
                eff_outputs = ("True" if node.tool_type == "Filter" else "Unique",)
            else:
                eff_outputs = all_outputs

            node_consts = node.metadata.get("workflow_constants") or static_consts
            self.expression_needs_file_exists = False
            lowered_res = self._lower_pure_node(
                node, cfg, arg_names, input_vars, consumed, eff_outputs, param_names, node_consts
            )
            if lowered_res is not None:
                body_lines, imps, p_used, rt_kwargs, can_inline, out_kinds = lowered_res
            else:
                body_lines = self._lower_via_registry_template(node, cfg, arg_names, eff_outputs)
                imps, p_used, rt_kwargs, can_inline, out_kinds = set(), set(), [], False, {}
            if self.expression_needs_file_exists:
                if self.is_macro:
                    raise UnsupportedLowering(f"{node.tool_type} #{node_id} needs a FileExists binding in a reusable macro")
                self.needs_file_exists = True
                rt_kwargs = [*rt_kwargs, "operations"]

            self.pipeline_imports |= imps
            fn_stem = self._stage_name(node, cfg)
            fn_name = alloc_func(fn_stem)

            out_vars: list[str] = []
            for anch in eff_outputs:
                suffix = "" if len(eff_outputs) == 1 else "_" + {"True": "matched", "False": "rejected"}.get(anch, _ident(anch))
                v_name = alloc_var(f"{fn_name}{suffix}_df")
                out_vars.append(v_name)
                var_by_anchor[(node_id, anch)] = v_name
                if len(eff_outputs) == 1 and out_kinds:
                    self.column_kinds_by_var[v_name] = out_kinds
                elif anch in {"True", "False", "Unique", "Duplicates"} and out_kinds:
                    self.column_kinds_by_var[v_name] = out_kinds

            guards = self._build_guards(node, by_id, var_by_anchor, param_names, container_guards)
            for g_p in self._guard_params(node, by_id, param_names):
                p_used.add(g_p)

            audit_lbl, audit_sum = self._describe_node_audit(node, cfg)
            op = _CompiledOp(
                node_id=node_id,
                source_tool_id=node.source_tool_id,
                tool_type=node.tool_type,
                func_name=fn_name,
                input_vars=input_vars,
                arg_names=arg_names,
                output_anchors=eff_outputs,
                output_vars=out_vars,
                param_kwargs=sorted(p_used - set(self._guard_params(node, by_id, param_names))),
                runtime_kwargs=rt_kwargs,
                body_lines=body_lines,
                imports=imps,
                can_inline_linear=can_inline and not guards and len(arg_names) == 1 and len(eff_outputs) == 1,
                guards=guards,
                audit_label=audit_lbl,
                audit_summary=audit_sum,
            )
            compiled_ops[node_id] = op
            orchestration_lines.append(f"    __OP__:{node_id}")

        # Fuse cohesive linear blocks (e.g. Formula -> single-branch Filter -> projection Select,
        # or Summarize -> Sort) into clean, readable stage functions!
        orchestration_lines, stage_mappings = self._emit_grouped_stages(
            orchestration_lines, compiled_ops, consumers_count
        )
        mapping_entries.extend(stage_mappings)

        # Collect terminal non-sink frames (for pure-transform workflows & Macro bodies)
        terminals = {
            f"{nid}:{anchor}": var_name
            for (nid, anchor), var_name in var_by_anchor.items()
            if not consumers_count.get((nid, anchor))
        }
        terminal_items = ", ".join(f"{key!r}: {var}" for key, var in terminals.items())

        io_imports = sorted(used_io_helpers)
        all_imports = set(self.pipeline_imports)
        entry_name = "run_pipeline" if self.is_macro else "transform"
        if not self.is_macro:
            has_sinks = "write_output_table" in used_io_helpers
            run_lines = [
                "def _transform(read_table, params, operations, *, audit=None, write_result=None):",
                *(["    results = {}"] if has_sinks else []),
                *orchestration_lines,
            ]
            if has_sinks:
                run_lines.append("    return results")
            else:
                run_lines.append(f"    return {{{terminal_items}}}")
            final_keys = sink_keys if has_sinks else list(terminals)
            return_expr = f"results.get({final_keys[0]!r})" if len(final_keys) == 1 else "results"
            run_lines += [
                "",
                "",
                "def transform(tables, *, parameters=None, references=None, operations=None):",
                '    """Apply workflow rules to in-memory tables and return the final result."""',
                '    sources = {"inputs": tables, "references": references or {}}',
                "",
                "    def read_table(section, key, _label):",
                "        return sources[section][key]",
                "",
                "    results = _transform(read_table, parameters or {}, operations or {})",
                f"    return {return_expr}",
            ]
            if compiled_ops:
                run_lines = [
                    "def _run_step(audit, name, tool, description, func, *args, **kwargs):",
                    "    if audit is None:",
                    "        return func(*args, **kwargs)",
                    "    return audit.run_step(name, tool, description, func, *args, **kwargs)",
                    "",
                    "",
                    *run_lines,
                ]
            io_block = ""
        else:
            run_lines = [
                "def run_pipeline(config: dict) -> dict:",
                '    params = config.get("parameters", {})',
            ]
            if "write_output_table" in used_io_helpers:
                run_lines.append("    written_outputs = {}")
            run_lines.extend(orchestration_lines)
            run_lines.append('    return {"frames": {' + terminal_items + "}}")

        if self.is_macro and io_imports:
            io_block = (
                "if __package__:\n"
                f"    from .io_utils import {', '.join(io_imports)}\n"
                "else:\n"
                f"    from io_utils import {', '.join(io_imports)}"
            )
        else:
            io_block = ""

        if self.linker.imports:
            all_imports |= {imp for imp in self.linker.imports if not imp.startswith("from __future__")}
        helper_names = sorted(self.linker.definitions.keys())
        if helper_names:
            helper_import_block = (
                "if __package__:\n"
                f"    from .helpers import {', '.join(helper_names)}\n"
                "else:\n"
                f"    from helpers import {', '.join(helper_names)}"
            )
        else:
            helper_import_block = ""

        # Fix relative macro imports for dual package/script execution if any
        macro_imports = sorted(imp for imp in all_imports if imp.startswith("from .macros."))
        all_imports -= set(macro_imports)
        if macro_imports:
            rel_m = "\n    ".join(macro_imports)
            abs_m = "\n    ".join(imp.replace("from .macros.", "from macros.") for imp in macro_imports)
            macro_import_block = f"if __package__:\n    {rel_m}\nelse:\n    {abs_m}"
        else:
            macro_import_block = ""

        future_imp = "from __future__ import annotations"
        other_imps = sorted(all_imports - {future_imp})
        header_parts = [
            '"""Modular native Python data pipeline. Configuration lives in config.toml."""',
            future_imp,
        ]
        if other_imps:
            header_parts.append("\n".join(other_imps))
        for block in (io_block, helper_import_block, macro_import_block):
            if block:
                header_parts.append(block)

        stage_blocks = [code for _, _, code in self.stage_defs]
        full_source = "\n\n".join(header_parts) + "\n\n\n" + "\n\n\n".join([*stage_blocks, "\n".join(run_lines)]) + "\n"

        # Compute line numbers for node -> stage function mapping
        src_lines = full_source.splitlines()
        line_by_fn = {
            fn_name: next((i + 1 for i, ln in enumerate(src_lines) if ln.startswith(f"def {fn_name}(")), 1)
            for fn_name, _, _ in self.stage_defs
        }
        line_by_fn["run_pipeline"] = next(
            (i + 1 for i, ln in enumerate(src_lines) if ln.startswith(f"def {entry_name}(")), 1
        )
        if not self.is_macro:
            for entry in mapping_entries:
                if entry["function"] == "run_pipeline":
                    entry["function"] = entry_name
            line_by_fn[entry_name] = line_by_fn["run_pipeline"]
        for entry in mapping_entries:
            entry["line"] = line_by_fn.get(entry["function"], 1)

        if not self.is_macro:
            self.runner_source = render_runner_py(self.config_spec, io_imports, self._link_operations())
        return full_source, mapping_entries

    def _link_operations(self) -> dict[str, str]:
        from alteryx2python.tools.delivery import run_checked_command
        from alteryx2python.tools.dynamicinput import read_file_list

        helpers = {}
        if any(key.startswith("dynamic_input_") for key in self.config_spec.operations):
            helpers["dynamic"] = self.linker.function(read_file_list)
        if any(key.startswith("directory_") for key in self.config_spec.operations):
            from alteryx2python.tools.directory import directory_frame

            helpers["directory"] = self.linker.function(directory_frame)
        if self.needs_commands:
            helpers["command"] = self.linker.function(run_checked_command)
        if self.needs_file_exists:
            from alteryx2python.expressions.functions import _file_exists

            helpers["file_exists"] = self.linker.function(_file_exists)
        if self.needs_render_xlsx:
            from alteryx2python.tools.delivery import render_xlsx_tables

            helpers["render_xlsx"] = self.linker.function(render_xlsx_tables)
        return helpers

    def _stage_name(self, node: NodeIR, cfg: dict[str, Any]) -> str:
        ann = _annotation_name(node)
        if ann:
            return ann
        kind = node.tool_type
        if kind == "Select":
            cols = [
                f.get("rename") or f["source"]
                for f in cfg.get("select_fields", [])
                if f.get("selected", True) and f.get("source") != "*Unknown"
            ]
            return "select_" + "_and_".join(cols[:2]) if cols else "select_columns"
        if kind == "Formula":
            cols = [f["field"] for f in cfg.get("formula_fields", []) if f.get("enabled", True)]
            return "compute_" + "_and_".join(cols[:2]) if cols else "compute_fields"
        if kind == "Filter":
            return "filter_rows"
        if kind == "Summarize":
            cols = [f["field"] for f in cfg.get("summarize_fields", []) if f.get("action") == "GroupBy"]
            return "summarize_by_" + "_and_".join(cols[:2]) if cols else "summarize_rows"
        if kind == "Sort":
            cols = [f["field"] for f in cfg.get("sort_fields", [])]
            return "sort_by_" + "_and_".join(cols[:2]) if cols else "sort_rows"
        if kind == "Join":
            return "join_streams"
        if kind == "Union":
            return "union_streams"
        if kind == "Unique":
            return "deduplicate_rows"
        return kind.lower()

    def _guard_params(self, node: NodeIR, by_id: dict[str, NodeIR], param_names: dict[str, str]) -> list[str]:
        found: list[str] = []
        parent = node.config.get("container_id") or node.config.get("normalized", {}).get("container_id")
        while parent and parent in by_id:
            container = by_id[parent]
            dp = container.metadata.get("disabled_parameter")
            if dp and dp in param_names:
                found.append(param_names[dp])
            parent = container.config.get("container_id") or container.config.get("normalized", {}).get("container_id")
        return found

    def _build_guards(
        self,
        node: NodeIR,
        by_id: dict[str, NodeIR],
        var_by_anchor: dict[tuple[str, str], str],
        param_names: dict[str, str],
        container_guards_fn,
    ) -> list[str]:
        guards = container_guards_fn(node, by_id, self.workflow.edges)
        conds = ["False" if g is None else f"not {var_by_anchor[g]}.empty" for g in guards]
        for gp in self._guard_params(node, by_id, param_names):
            conds.append(f'not params[{gp!r}]')
        return conds

    def _emit_grouped_stages(
        self,
        raw_orchestration: list[str],
        compiled_ops: dict[str, _CompiledOp],
        consumers_count: dict[tuple[str, str], int],
    ) -> tuple[list[str], list[dict[str, Any]]]:
        """Group linear business derivation blocks (Formula+Filter+Select or Summarize+Sort) cleanly."""
        final_orch: list[str] = []
        mappings: list[dict[str, Any]] = []
        idx = 0

        while idx < len(raw_orchestration):
            line = raw_orchestration[idx]
            if not line.startswith("    __OP__:"):
                final_orch.append(line)
                idx += 1
                continue

            nid = line.split(":", 1)[1]
            first_op = compiled_ops[nid]
            group = [first_op]
            idx += 1

            # Group cohesive linear business derivation (Formula -> Filter -> Select)
            # OR Summarize -> Sort pairs! Keep input preparation Selects standalone for clarity.
            while idx < len(raw_orchestration) and raw_orchestration[idx].startswith("    __OP__:"):
                next_id = raw_orchestration[idx].split(":", 1)[1]
                cand = compiled_ops[next_id]
                prev = group[-1]
                if prev.guards or cand.guards:
                    break
                if len(prev.output_vars) != 1 or len(cand.input_vars) != 1:
                    break
                prev_out_anchor = prev.output_anchors[0]
                if consumers_count.get((prev.node_id, prev_out_anchor), 0) != 1:
                    break
                if next(iter(cand.input_vars.values())) != prev.output_vars[0]:
                    break

                # Rule A: Summarize -> Sort cohesive aggregation stage
                if prev.tool_type == "Summarize" and cand.tool_type == "Sort" and len(group) == 1:
                    group.append(cand)
                    idx += 1
                    break

                # Rule B: Derivation + Filter + terminal Select block (keep initial input Select separate!)
                if (
                    prev.can_inline_linear
                    and cand.can_inline_linear
                    and prev.tool_type in {"Formula", "Filter"}
                    and cand.tool_type in {"Formula", "Filter", "Select"}
                    and sum(len(g.body_lines) for g in group) + len(cand.body_lines) <= 28
                ):
                    group.append(cand)
                    idx += 1
                    continue

                break

            if len(group) == 1:
                fn_code = self._render_single_stage(first_op)
                self.stage_defs.append((first_op.func_name, [first_op.node_id], fn_code))
                final_orch.extend(self._render_stage_call(first_op))
                mappings.append({
                    "node_id": first_op.node_id,
                    "source_tool_id": first_op.source_tool_id,
                    "tool_type": first_op.tool_type,
                    "function": first_op.func_name,
                    "outputs": list(first_op.output_anchors),
                    "variables": dict(zip(first_op.output_anchors, first_op.output_vars)),
                })
            else:
                fn_name, fn_code, combined_op = self._render_fused_stage(group)
                self.stage_defs.append((fn_name, [g.node_id for g in group], fn_code))
                final_orch.extend(self._render_stage_call(combined_op))
                for g in group:
                    mappings.append({
                        "node_id": g.node_id,
                        "source_tool_id": g.source_tool_id,
                        "tool_type": g.tool_type,
                        "function": fn_name,
                        "outputs": list(g.output_anchors),
                        "variables": dict(zip(g.output_anchors, g.output_vars)),
                    })

        return final_orch, mappings

    def _render_single_stage(self, op: _CompiledOp) -> str:
        pos_args = [f"{a}: pd.DataFrame" for a in op.arg_names.values()]
        kw_args = [*op.runtime_kwargs, *op.param_kwargs]
        sig_parts = list(pos_args)
        if kw_args:
            sig_parts.append("*")
            sig_parts.extend(kw_args)
        ret_ann = "pd.DataFrame" if len(op.output_vars) == 1 else ("tuple[" + ", ".join("pd.DataFrame" for _ in op.output_vars) + "]" if op.output_vars else "None")
        header = f"def {op.func_name}({', '.join(sig_parts)}) -> {ret_ann}:"
        body = textwrap.indent("\n".join(op.body_lines), "    ")
        return f"{header}\n{body}"

    def _render_fused_stage(self, group: list[_CompiledOp]) -> tuple[str, str, _CompiledOp]:
        first, last = group[0], group[-1]
        fn_name = first.func_name
        in_arg = next(iter(first.arg_names.values()))
        all_params = sorted({p for g in group for p in g.param_kwargs})
        all_rt = sorted({r for g in group for r in g.runtime_kwargs})

        body_lines: list[str] = []
        current_var = in_arg
        for step_idx, g in enumerate(group):
            step_arg = next(iter(g.arg_names.values()))
            lines = list(g.body_lines)
            # Rename step's input variable to current_var cleanly via AST
            step_mod = ast.parse("def _tmp():\n" + textwrap.indent("\n".join(lines), "    "))
            fn_ast = step_mod.body[0]

            class _Rebind(ast.NodeTransformer):
                def visit_Name(self, n: ast.Name):
                    if n.id == step_arg:
                        return ast.copy_location(ast.Name(id=current_var, ctx=n.ctx), n)
                    return n

            fn_ast = _Rebind().visit(fn_ast)
            stmts = fn_ast.body
            is_last = step_idx == len(group) - 1
            if not is_last:
                # Replace trailing `return expr` with `df = expr`
                ret_stmt = stmts[-1]
                assert isinstance(ret_stmt, ast.Return) and ret_stmt.value is not None
                next_var = "df"
                for stmt in stmts[:-1]:
                    body_lines.append(ast.unparse(ast.fix_missing_locations(stmt)))
                ret_code = ast.unparse(ast.fix_missing_locations(ret_stmt.value))
                if ret_code != next_var:
                    body_lines.append(f"{next_var} = {ret_code}")
                current_var = next_var
            else:
                for stmt in stmts:
                    body_lines.append(ast.unparse(ast.fix_missing_locations(stmt)))

        sig_parts = [f"{in_arg}: pd.DataFrame"]
        kw_args = [*all_rt, *all_params]
        if kw_args:
            sig_parts.append("*")
            sig_parts.extend(kw_args)
        header = f"def {fn_name}({', '.join(sig_parts)}) -> pd.DataFrame:"
        code = f"{header}\n" + textwrap.indent("\n".join(body_lines), "    ")
        fused_tools = "->".join(g.tool_type for g in group)
        fused_ids = ",".join(str(g.source_tool_id or g.node_id) for g in group)
        fused_summary = " -> ".join(g.audit_summary for g in group if g.audit_summary)
        combined = _CompiledOp(
            node_id=last.node_id,
            source_tool_id=last.source_tool_id,
            tool_type=last.tool_type,
            func_name=fn_name,
            input_vars=first.input_vars,
            arg_names=first.arg_names,
            output_anchors=last.output_anchors,
            output_vars=last.output_vars,
            param_kwargs=all_params,
            runtime_kwargs=all_rt,
            body_lines=body_lines,
            audit_label=f"{fused_tools} #{fused_ids}",
            audit_summary=fused_summary,
        )
        return fn_name, code, combined

    def _render_stage_call(self, op: _CompiledOp) -> list[str]:
        pos_vals = list(op.input_vars.values())
        kw_vals = [*(f"{r}={r}" for r in op.runtime_kwargs), *(f'{p}=params[{p!r}]' for p in op.param_kwargs)]
        all_args = [*pos_vals, *kw_vals]
        if self.is_macro or op.tool_type in {"MacroInput", "MacroBoundaryInput", "MacroOutput"}:
            call_expr = f"{op.func_name}({', '.join(all_args)})"
        else:
            arg_tail = (", " + ", ".join(all_args)) if all_args else ""
            call_expr = f"_run_step(audit, {op.func_name!r}, {op.audit_label!r}, {op.audit_summary!r}, {op.func_name}{arg_tail})"
        lhs = ", ".join(op.output_vars)
        stmt = f"{lhs} = {call_expr}" if lhs else call_expr
        if not op.guards:
            return [f"    {stmt}"]
        lines = [f"    if {' and '.join(op.guards)}:", f"        {stmt}"]
        if op.output_vars or not self.is_macro:
            lines.append("    else:")
            if not self.is_macro:
                lines.append("        if audit is not None:")
                lines.append(f"            audit.skip_step({op.func_name!r}, {op.audit_label!r}, {op.audit_summary!r})")
            if op.output_vars:
                fallback_src = next(iter(op.input_vars.values()), None)
                for v in op.output_vars:
                    lines.append(f"        {v} = {fallback_src}.iloc[:0].copy()" if fallback_src else f"        {v} = pd.DataFrame()")
        return lines


class ModularPackageGenerator:
    """Compile WorkflowIR into an adaptive, config-decoupled native Python package."""

    def generate(
        self,
        workflow: WorkflowIR,
        *,
        answers: dict[str, Any] | None = None,
        constants: dict[str, Any] | None = None,
        parameter_mode: str = "dynamic",
        delivery_profile: str | None = None,
        log_event_ids: tuple[str, ...] | list[str] = (),
        input_bindings: dict[str, str] | None = None,
    ) -> PackageArtifact:
        from alteryx2python.runtime.variables import bind_workflow_variables

        log_event_ids = tuple(log_event_ids)
        original = deepcopy(workflow)

        if parameter_mode != "dynamic":
            raise UnsupportedLowering("Phase 2 packages require dynamic parameter bindings")
        if workflow.metadata.get("configuration_applied"):
            raise UnsupportedLowering("Phase 2 requires workflow IR before app answers are applied")
        for node in workflow.nodes:
            cfg = node.config.get("normalized", node.config)
            if node.tool_type == "DynamicInput" and str(cfg.get("read_list_field", "")).startswith("__a2p_path_"):
                raise UnsupportedLowering(
                    f"DynamicInput #{node.node_id} uses a replay-only path field. Compile the original workflow."
                )
        prepared, param_exprs, param_specs = prepare_parameters(workflow, answers, constants)

        prepared = bind_workflow_variables(prepared, constants)
        if input_bindings:
            from alteryx2python.input_bindings import apply_input_bindings

            apply_input_bindings(prepared, input_bindings)
            prepared.metadata["parameter_bindings"] = [
                item
                for item in prepared.metadata.get("parameter_bindings", [])
                if item["kind"] != "file" or item["node_id"] not in input_bindings
            ]

        opt = optimize_workflow_ir(
            prepared,
            parameters=param_specs,
            parameter_bindings=prepared.metadata.get("parameter_bindings", []),
            parameter_expressions=param_exprs,
        )

        return self._emit_package(
            original, opt, delivery_profile=delivery_profile, log_event_ids=log_event_ids
        )

    def _emit_package(
        self,
        original: WorkflowIR,
        opt: OptimizationResult,
        *,
        delivery_profile: str | None,
        log_event_ids: tuple[str, ...],
    ) -> PackageArtifact:
        config_spec = extract_config(
            opt,
            original_workflow=original,
            delivery_profile=delivery_profile,
            log_event_ids=log_event_ids,
        )

        helper_linker = SourceLinker()
        emitter = _SubgraphEmitter(
            opt,
            config_spec,
            delivery_profile=delivery_profile,
            helper_linker=helper_linker,
        )
        pipeline_py, node_mappings = emitter.compile_pipeline()

        # Emit macro modules ONLY when reusable or loop macros exist
        macro_files: dict[str, str] = {}
        if opt.reusable_macros or opt.loop_macros:
            macro_files["macros/__init__.py"] = '"""Reusable and iterative/batch macro modules."""\n'
            for m_key, r_spec in sorted(opt.reusable_macros.items()):
                macro_files[f"macros/{m_key}.py"] = self._render_reusable_macro_module(r_spec, helper_linker, delivery_profile)
            for m_key, l_spec in sorted(opt.loop_macros.items()):
                macro_files[f"macros/{m_key}.py"] = self._render_loop_macro_module(l_spec, helper_linker, delivery_profile)

        files: dict[str, str] = {
            "__init__.py": render_init_py(),
            "__main__.py": render_main_py(),
            "config.toml": config_spec.to_toml(),
            "audit_utils.py": render_audit_utils_py(),
            "pipeline.py": pipeline_py,
            "runner.py": emitter.runner_source,
            "cli.py": render_cli_py(config_spec, has_messages=emitter.has_messages),
            "io_utils.py": render_io_utils_py(
                config_spec,
                needs_excel_in=emitter.needs_excel_in,
                needs_excel_out=emitter.needs_excel_out,
                needs_render_html=emitter.needs_render_html,
                needs_render_xlsx=emitter.needs_render_xlsx,
                needs_email=emitter.needs_email,
                needs_commands=emitter.needs_commands,
                needs_events=bool(config_spec.events),
            ),
        }

        if helper_linker.definitions:
            files["helpers.py"] = '"""Specialized pure helper routines."""\n\n' + helper_linker.render() + "\n"

        files.update(macro_files)
        files.update(config_spec.reference_files)

        # Safety gate: zero project imports or graph/expression interpreters in any generated .py file!
        forbidden_tokens = ("run_workflow_graph", "WorkflowContext", "NODE_DATA", "EDGE_DATA", "evaluate_expression", "parse_expression")
        for rel_path, content in files.items():
            if not rel_path.endswith(".py"):
                continue
            parsed = ast.parse(content, filename=rel_path)
            for item in ast.walk(parsed):
                mods = (
                    [item.module or ""]
                    if isinstance(item, ast.ImportFrom)
                    else ([alias.name for alias in item.names] if isinstance(item, ast.Import) else [])
                )
                if any(m.startswith(("alteryx2python", "alteryx_runtime")) for m in mods):
                    raise UnsupportedLowering(f"Project dependency leaked into generated file {rel_path}")
            if any(tok in content for tok in forbidden_tokens):
                raise UnsupportedLowering(f"Runtime interpreter leaked into generated file {rel_path}")

        # Attach provenance mapping for eliminated/fused source nodes so `demo deliver` can locate every original node_id!
        mapped_by_id = {m["node_id"]: m for m in node_mappings}
        for orig_id, prov in opt.provenance.items():
            if orig_id in mapped_by_id:
                continue
            target_id = prov.get("target_node_id")
            target_entry = mapped_by_id.get(target_id) if target_id else None
            node_mappings.append({
                "node_id": orig_id,
                "source_tool_id": orig_id,
                "tool_type": prov.get("reason", "optimized"),
                "function": target_entry["function"] if target_entry else "transform",
                "line": target_entry["line"] if target_entry else 1,
                "optimization": prov,
                "outputs": [],
                "variables": {},
            })

        file_hashes = {k: hashlib.sha256(v.encode("utf-8")).hexdigest() for k, v in sorted(files.items())}
        manifest: dict[str, Any] = {
            "format_version": 2,
            "template_version": PACKAGE_TEMPLATE_VERSION,
            "artifact_kind": "package",
            "entrypoint": "pipeline.py",
            "cli_entrypoint": "cli.py",
            "config_file": "config.toml",
            "workflow_id": original.workflow_id,
            "source_sha256": original.source_hash,
            "generated_sha256": file_hashes["pipeline.py"],
            "file_sha256": file_hashes,
            "delivery_profile": delivery_profile,
            "config_schema": config_spec.to_dict(),
            "parameter_mode": "dynamic",
            "optimization_provenance": opt.provenance,
            "native_equivalence": "unverified",
            "python_differential": "unverified",
            "nodes": sorted(node_mappings, key=lambda x: str(x["node_id"])),
        }
        return PackageArtifact(
            files=files,
            manifest=manifest,
            workflow=original,
            config_spec=config_spec,
        )

    def _render_reusable_macro_module(
        self,
        spec: MacroSubgraphSpec,
        helper_linker: SourceLinker,
        delivery_profile: str | None,
    ) -> str:
        sub_opt = OptimizationResult(
            workflow=spec.workflow,
            parameters=spec.parameters,
            parameter_expressions=spec.parameter_expressions,
        )
        sub_cfg = extract_config(sub_opt, delivery_profile=delivery_profile)
        sub_emitter = _SubgraphEmitter(
            sub_opt,
            sub_cfg,
            delivery_profile=delivery_profile,
            helper_linker=helper_linker,
            is_macro=True,
        )
        body_py, _ = sub_emitter.compile_pipeline()
        in_args = [_ident(a, "input") + "_df" for a in spec.input_anchors] or ["input_df"]
        param_defs = [f"{py_n}={val!r}" for py_n, val in sub_cfg.parameters.items()]
        sig = ", ".join([*in_args, *(["*", *param_defs] if param_defs else [])])

        # Find boundary inputs or first consumers in macro workflow
        wrapper = [
            f"\n\ndef run_{spec.macro_key}({sig}):",
            "    cfg = {'inputs': {}, 'outputs': {}, 'parameters': {" + ", ".join(f"{py_n!r}: {py_n}" for py_n in sub_cfg.parameters) + "}, 'runtime': {}}",
            "    res = _run_macro_body(cfg, " + ", ".join(in_args) + ")",
            "    return res",
        ]
        return self._adapt_macro_body_module(body_py, spec.workflow, spec.input_anchors, spec.output_anchors, helper_linker) + "\n".join(wrapper) + "\n"

    def _render_loop_macro_module(
        self,
        spec: LoopMacroSpec,
        helper_linker: SourceLinker,
        delivery_profile: str | None,
    ) -> str:
        sub_opt = OptimizationResult(
            workflow=spec.workflow,
            parameters=spec.parameters,
            parameter_expressions=spec.parameter_expressions,
        )
        sub_cfg = extract_config(sub_opt, delivery_profile=delivery_profile)
        sub_emitter = _SubgraphEmitter(
            sub_opt,
            sub_cfg,
            delivery_profile=delivery_profile,
            helper_linker=helper_linker,
            is_macro=True,
        )
        if spec.kind == "batch":
            from alteryx2python.tools.macro_engine import concat_batch_frames

            concat_batch = helper_linker.function(concat_batch_frames)
        body_py, _ = sub_emitter.compile_pipeline()
        all_outs = list(spec.output_anchors)
        if spec.kind == "iterative" and spec.iteration_output and spec.iteration_output not in all_outs:
            all_outs = [spec.iteration_output, *all_outs]
        adapted = self._adapt_macro_body_module(body_py, spec.workflow, spec.input_anchors, all_outs, helper_linker, as_dict=True)

        in_args = [_ident(a, "input") + "_df" for a in spec.input_anchors]
        if spec.kind == "batch":
            ctrl_py = sub_cfg.python_param_names.get(spec.control_param or "", _ident(spec.control_param or "control", "param"))
            loop_fn = textwrap.dedent(
                f'''

                def run_{spec.macro_key}_batch(control_df: pd.DataFrame, {", ".join(f"{a}: pd.DataFrame" for a in in_args)}, *, control_field: str | None = None):
                    col = control_field
                    if col is None and len(control_df.columns) == 1:
                        col = control_df.columns[0]
                    if col not in control_df:
                        raise ValueError("Batch macro requires a valid control_field")
                    collected: dict[str, list[pd.DataFrame]] = {{name: [] for name in {spec.output_anchors!r}}}
                    for ctrl_val in control_df[col]:
                        cfg = {{"inputs": {{}}, "outputs": {{}}, "parameters": {{{ctrl_py!r}: ctrl_val}}, "runtime": {{}}}}
                        step_out = _run_macro_body(cfg, {", ".join(in_args)})
                        for name in {spec.output_anchors!r}:
                            collected[name].append(step_out[name])
                    results = []
                    for name, frames in collected.items():
                        if not frames:
                            columns = {spec.output_columns!r}.get(name)
                            if not columns:
                                raise ValueError("Empty batch control needs an independently declared output schema")
                            frames = [pd.DataFrame(columns=columns)]
                        results.append({concat_batch}(frames, {spec.output_mode!r}))
                    return results[0] if len(results) == 1 else tuple(results)
                '''
            )
            return adapted + loop_fn

        iter_in_idx = spec.input_anchors.index(spec.iteration_input) if spec.iteration_input in spec.input_anchors else 0
        iter_var = in_args[iter_in_idx] if in_args else "iter_df"
        loop_fn = textwrap.dedent(
            f'''

            def run_{spec.macro_key}_iterative({", ".join(f"{a}: pd.DataFrame" for a in in_args)}):
                collected: dict[str, list[pd.DataFrame]] = {{name: [] for name in {spec.output_anchors!r}}}
                current = {iter_var}.copy()
                for _ in range({spec.iteration_limit}):
                    {iter_var} = current
                    cfg = {{"inputs": {{}}, "outputs": {{}}, "parameters": {{}}, "runtime": {{}}}}
                    step_out = _run_macro_body(cfg, {", ".join(in_args)})
                    for name in {spec.output_anchors!r}:
                        if name in step_out:
                            collected[name].append(step_out[name])
                    next_frame = step_out[{spec.iteration_output!r}]
                    if next_frame.empty:
                        break
                    current = next_frame
                else:
                    if {spec.limit_behavior!r} != "Ignore":
                        raise ValueError("Iterative macro iteration limit reached")
                results = [
                    pd.concat(collected[name], ignore_index=True) if collected[name] else pd.DataFrame()
                    for name in {spec.output_anchors!r}
                ]
                return results[0] if len(results) == 1 else tuple(results)
            '''
        )
        return adapted + loop_fn

    def _adapt_macro_body_module(
        self,
        body_py: str,
        macro_wf: WorkflowIR,
        input_anchors: list[str],
        output_anchors: list[str],
        helper_linker: SourceLinker,
        *,
        as_dict: bool = False,
    ) -> str:
        """Rewrite macro body's run_pipeline(config) into _run_macro_body(config, *inputs)."""
        in_nodes = [n for n in macro_wf.nodes if n.tool_type in {"MacroInput", "MacroBoundaryInput"}]
        out_nodes = [n for n in macro_wf.nodes if n.tool_type == "MacroOutput"]
        in_arg_names = [_ident(a, "input") + "_df" for a in input_anchors] or ["input_df"]
        anchor_to_arg = dict(zip(input_anchors, in_arg_names))

        # Map MacroInput stage function name -> corresponding input parameter name
        fn_by_node_id: dict[str, str] = {}
        # Also map MacroOutput node_id -> output anchor name
        out_name_to_id: dict[str, str] = {}
        for idx, m_out in enumerate(out_nodes):
            cfg_name = m_out.config.get("normalized", m_out.config).get("name") or (
                output_anchors[idx] if idx < len(output_anchors) else "Output"
            )
            out_name_to_id[cfg_name] = m_out.node_id

        tree = ast.parse(body_py)
        # Fix helper imports inside macros/ subpackage (`if __package__ and "." in __package__: from ..helpers ... else: from helpers ...`)
        for node in tree.body:
            if isinstance(node, ast.If) and any(
                isinstance(s, ast.ImportFrom) and s.module in {"helpers", "io_utils"} and s.level == 1
                for s in node.body
            ):
                node.test = ast.BoolOp(
                    op=ast.And(),
                    values=[
                        ast.Name(id="__package__", ctx=ast.Load()),
                        ast.Compare(
                            left=ast.Constant(value="."),
                            ops=[ast.In()],
                            comparators=[ast.Name(id="__package__", ctx=ast.Load())],
                        ),
                    ],
                )
                for stmt in node.body:
                    if isinstance(stmt, ast.ImportFrom) and stmt.module in {"helpers", "io_utils"} and stmt.level == 1:
                        stmt.level = 2

        in_fn_defs = [
            stmt.name
            for stmt in tree.body
            if isinstance(stmt, ast.FunctionDef) and stmt.name != "run_pipeline" and len(stmt.args.args) == 0
        ]
        for idx, m_in in enumerate(in_nodes):
            in_name = m_in.config.get("normalized", m_in.config).get("name") or (
                input_anchors[idx] if idx < len(input_anchors) else "Input"
            )
            if idx < len(in_fn_defs):
                fn_by_node_id[in_fn_defs[idx]] = anchor_to_arg.get(in_name, in_arg_names[min(idx, len(in_arg_names) - 1)])

        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and node.name == "run_pipeline":
                node.name = "_run_macro_body"
                node.args.args.extend(ast.arg(arg=name) for name in in_arg_names)

                ret_stmt = node.body[-1]
                frame_var_by_nid: dict[str, str] = {}
                if isinstance(ret_stmt, ast.Return) and isinstance(ret_stmt.value, ast.Dict):
                    for k_node, v_node in zip(ret_stmt.value.keys, ret_stmt.value.values):
                        if isinstance(k_node, ast.Constant) and k_node.value == "frames" and isinstance(v_node, ast.Dict):
                            for fk, fv in zip(v_node.keys, v_node.values):
                                if isinstance(fk, ast.Constant) and isinstance(fv, ast.Name):
                                    nid_part = str(fk.value).split(":", 1)[0]
                                    frame_var_by_nid[nid_part] = fv.id

                new_body: list[ast.stmt] = []
                in_idx = 0
                for stmt in node.body[:-1]:
                    if (
                        isinstance(stmt, ast.Assign)
                        and isinstance(stmt.value, ast.Call)
                        and isinstance(stmt.value.func, ast.Name)
                        and not stmt.value.args
                        and in_idx < len(in_arg_names)
                    ):
                        mapped_arg = fn_by_node_id.get(stmt.value.func.id, in_arg_names[in_idx])
                        stmt.value = ast.Call(
                            func=ast.Attribute(value=ast.Name(id=mapped_arg, ctx=ast.Load()), attr="copy", ctx=ast.Load()),
                            args=[],
                            keywords=[],
                        )
                        in_idx += 1
                    new_body.append(stmt)

                out_vars: dict[str, str] = {}
                for o_name in output_anchors:
                    nid = out_name_to_id.get(o_name)
                    if nid and nid in frame_var_by_nid:
                        out_vars[o_name] = frame_var_by_nid[nid]
                    elif frame_var_by_nid:
                        out_vars[o_name] = next(iter(frame_var_by_nid.values()))

                if as_dict:
                    ret_expr = ast.Dict(
                        keys=[ast.Constant(k) for k in out_vars],
                        values=[ast.Name(id=v, ctx=ast.Load()) for v in out_vars.values()],
                    )
                elif len(out_vars) == 1:
                    ret_expr = ast.Name(id=next(iter(out_vars.values())), ctx=ast.Load())
                else:
                    ret_expr = ast.Tuple(
                        elts=[ast.Name(id=v, ctx=ast.Load()) for v in out_vars.values()],
                        ctx=ast.Load(),
                    )
                new_body.append(ast.Return(value=ret_expr))
                node.body = new_body

        del helper_linker
        return ast.unparse(ast.fix_missing_locations(tree)) + "\n"

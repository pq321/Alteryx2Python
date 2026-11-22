"""Extract externalizable inputs, outputs, parameters, references, and events into config.toml."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
import io
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import tomllib
from typing import Any

import pandas as pd

from alteryx2python.generator.ir_optimizer import OptimizationResult
from alteryx2python.generator.source_linker import UnsupportedLowering
from alteryx2python.ir.models import NodeIR, WorkflowIR
from alteryx2python.tools.dbfileinput import (
    _delimiter as input_delimiter,
    _encoding as input_encoding,
    _file_attribute,
    _header_row,
    _import_line,
    _record_limit,
    _split_alteryx_file_reference,
    excel_selection_options,
)
from alteryx2python.tools.dbfileoutput import (
    _format_option,
    _line_ending,
    _max_records,
    xlsx_output_options,
)
from alteryx2python.tools.textinput import _infer_types, _normalize_row


def _slug(value: str, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value)).strip("_").lower()
    if not cleaned:
        return fallback
    return f"_{cleaned}" if cleaned[0].isdigit() else cleaned


def _pure_path(raw: str) -> PurePosixPath | PureWindowsPath:
    win = PureWindowsPath(raw)
    return win if win.drive or "\\" in raw else PurePosixPath(raw)


def _portable_relative_path(raw: str, base_dir: str | None, *, explicit_binding: bool = False) -> str:
    path = _pure_path(raw)
    if explicit_binding:
        return path.as_posix()
    if path.is_absolute():
        if not base_dir:
            raise UnsupportedLowering("External absolute input requires an explicit portable binding")
        try:
            rel = path.relative_to(_pure_path(str(base_dir)))
        except ValueError as exc:
            raise UnsupportedLowering("External absolute input requires an explicit portable binding") from exc
        return rel.as_posix()
    if path.anchor:
        raise UnsupportedLowering("Drive-relative input requires an explicit portable binding")
    return path.as_posix()


def _node_annotation(node: NodeIR) -> str:
    ann = node.metadata.get("annotation", {}).get("Name", "")
    if isinstance(ann, dict):
        ann = ann.get("text", "")
    return str(ann or "").strip()


@dataclass
class ConfigSpec:
    """Structured external configuration and extracted reference files for a package."""

    inputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    outputs: dict[str, dict[str, Any]] = field(default_factory=dict)
    parameters: dict[str, Any] = field(default_factory=dict)
    parameter_meta: dict[str, dict[str, Any]] = field(default_factory=dict)
    logging: dict[str, Any] = field(
        default_factory=lambda: {
            "enabled": True,
            "level": "INFO",
            "format": "text",
            "file": "",
        }
    )
    references: dict[str, dict[str, Any]] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    reference_files: dict[str, str] = field(default_factory=dict)  # rel POSIX path -> CSV text
    input_key_by_node: dict[str, str] = field(default_factory=dict)
    output_key_by_node: dict[str, str] = field(default_factory=dict)
    reference_key_by_node: dict[str, str] = field(default_factory=dict)
    python_param_names: dict[str, str] = field(default_factory=dict)  # logical/Question/User name -> python kwarg

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "inputs": self.inputs,
            "outputs": self.outputs,
            "parameters": self.parameters,
            "logging": self.logging,
        }
        if self.references:
            payload["references"] = self.references
        if self.events:
            payload["events"] = {"hooks": self.events}
        return payload

    def to_toml(self) -> str:
        text = _render_config_toml(self)
        # Guarantee round-trip validity with Python's built-in tomllib
        tomllib.loads(text)
        return text


def _toml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return json.dumps(str(value))
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_scalar(v) for v in value) + "]"
    if value is None:
        return '""'
    return json.dumps(str(value), ensure_ascii=False)


def _toml_key(key: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_-]+", key):
        return key
    return json.dumps(key, ensure_ascii=False)


def _render_table_entries(mapping: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    nested: list[tuple[str, dict[str, Any]]] = []
    for k, v in mapping.items():
        if v is None:
            continue
        if isinstance(v, dict):
            nested.append((k, v))
        else:
            lines.append(f"{_toml_key(k)} = {_toml_scalar(v)}")
    for k, sub in nested:
        inline_items = ", ".join(f"{_toml_key(sk)} = {_toml_scalar(sv)}" for sk, sv in sub.items() if sv is not None)
        lines.append(f"{_toml_key(k)} = {{ {inline_items} }}")
    return lines


def _render_config_toml(spec: ConfigSpec) -> str:
    blocks: list[str] = [
        "# Workflow runtime configuration (inputs, outputs, parameters, references, events).",
        "# Edit paths or parameter values here or supply an override file via --config.",
    ]

    blocks.append("\n[parameters]")
    if not spec.parameters:
        blocks.append("# No external runtime parameters.")
    for py_name, val in spec.parameters.items():
        meta = spec.parameter_meta.get(py_name, {})
        comment_parts: list[str] = []
        if meta.get("description"):
            comment_parts.append(str(meta["description"]))
        if meta.get("kind"):
            comment_parts.append(f"type={meta['kind']}")
        if meta.get("choices"):
            comment_parts.append(f"choices={meta['choices']!r}")
        if meta.get("minimum") is not None or meta.get("maximum") is not None:
            comment_parts.append(f"range=[{meta.get('minimum')}, {meta.get('maximum')}]")
        if comment_parts:
            blocks.append(f"# {' | '.join(comment_parts)}")
        blocks.append(f"{_toml_key(py_name)} = {_toml_scalar(val)}")

    if not spec.inputs:
        blocks.append("\n[inputs]")
    for key, entry in spec.inputs.items():
        blocks.append(f"\n[inputs.{_toml_key(key)}]")
        blocks.extend(_render_table_entries(entry))

    if not spec.outputs:
        blocks.append("\n[outputs]")
    for key, entry in spec.outputs.items():
        blocks.append(f"\n[outputs.{_toml_key(key)}]")
        blocks.extend(_render_table_entries(entry))

    for key, entry in spec.references.items():
        blocks.append(f"\n[references.{_toml_key(key)}]")
        blocks.extend(_render_table_entries(entry))

    for hook in spec.events:
        blocks.append("\n[[events.hooks]]")
        blocks.extend(_render_table_entries(hook))

    if spec.logging:
        blocks.append("\n[logging]")
        blocks.append("# Step-by-step pipeline audit logging (format: \"text\" or \"jsonl\"; level: \"DEBUG\", \"INFO\", \"WARNING\", \"ERROR\", \"OFF\").")
        blocks.extend(_render_table_entries(spec.logging))

    return "\n".join(blocks) + "\n"


def _unique_key(stem: str, used: set[str], fallback: str) -> str:
    base = _slug(stem, fallback)
    candidate, idx = base, 1
    while candidate in used:
        idx += 1
        candidate = f"{base}_{idx}"
    used.add(candidate)
    return candidate


def _extract_user_constants_used(workflow: WorkflowIR) -> dict[str, Any]:
    """Find User.* workflow constants referenced in active nodes or events."""
    all_consts = workflow.metadata.get("workflow_constants", {})
    if not all_consts:
        return {}
    user_consts = {k: v for k, v in all_consts.items() if k.startswith("User.")}
    if not user_consts:
        return {}
    haystack_parts = [str(workflow.source_xml or "")]
    for node in workflow.nodes:
        haystack_parts.append(json.dumps(node.config, default=str))
    haystack = "\n".join(haystack_parts)
    used: dict[str, Any] = {}
    for key, val in sorted(user_consts.items()):
        short = key.removeprefix("User.")
        if key in haystack or f"%User.{short}%" in haystack:
            used[key] = val
    return used


def extract_config(
    opt: OptimizationResult,
    *,
    original_workflow: WorkflowIR | None = None,
    delivery_profile: str | None = None,
    log_event_ids: tuple[str, ...] = (),
    alteryx_csv_outputs: set[str] | None = None,
) -> ConfigSpec:
    """Extract ConfigSpec and reference CSV files from an optimized WorkflowIR."""
    from alteryx2python.tools import delivery as delivery_tools
    from alteryx2python.workflow_events import (
        attachment_bindings,
        attachment_output,
        bind_logging_events,
        workflow_events,
    )

    workflow = opt.workflow
    source_wf = original_workflow or workflow
    spec = ConfigSpec()
    alteryx_csv_outputs = alteryx_csv_outputs or set()

    used_param_py: set[str] = {"config", "df", "input_dir", "output_dir"}
    # 1. Register Analytic App Questions & folded 1-row TextInput parameters
    for param in opt.parameters:
        orig_name = str(param["name"])
        base_py = _slug(param.get("python_name") or orig_name, "param")
        py_name = _unique_key(base_py, used_param_py, "param")
        spec.python_param_names[orig_name] = py_name
        spec.python_param_names[f"Question.{orig_name}"] = py_name
        default_val = param.get("default")
        if default_val is None:
            default_val = ""
        spec.parameters[py_name] = default_val
        spec.parameter_meta[py_name] = {
            "name": orig_name,
            "kind": param.get("kind", "TextBox"),
            "description": param.get("description", ""),
            "minimum": param.get("minimum"),
            "maximum": param.get("maximum"),
            "required": bool(param.get("required", False)),
            "choices": list(param.get("choices") or []),
            "expression_text": bool(param.get("expression_text", False)),
        }

    # 2. Register referenced User.* workflow constants into [parameters]
    for const_key, const_val in _extract_user_constants_used(workflow).items():
        short = const_key.removeprefix("User.")
        py_name = _unique_key(f"user_{_slug(short)}", used_param_py, "user_var")
        spec.python_param_names[const_key] = py_name
        spec.parameters[py_name] = const_val
        spec.parameter_meta[py_name] = {
            "name": const_key,
            "kind": "NumericUpDown" if isinstance(const_val, (int, float)) and not isinstance(const_val, bool) else (
                "BooleanGroup" if isinstance(const_val, bool) else "TextBox"
            ),
            "description": f"Workflow constant {const_key}",
            "required": False,
            "choices": [],
        }

    # Add as_of parameter if any expression calls DateTimeNow / DateTimeToday
    wf_dump = json.dumps([n.config for n in workflow.nodes], default=str).upper()
    if "DATETIMENOW" in wf_dump or "DATETIMETODAY" in wf_dump or any(n.tool_type == "DateTimeNow" for n in workflow.nodes):
        py_name = _unique_key("as_of", used_param_py, "as_of")
        spec.python_param_names["__as_of__"] = py_name
        spec.parameters[py_name] = ""
        spec.parameter_meta[py_name] = {
            "name": "as_of",
            "kind": "TextBox",
            "description": "Optional ISO timestamp override for DateTimeNow/DateTimeToday",
            "required": False,
            "choices": [],
        }

    file_param_by_node: dict[str, str] = {}
    for binding in opt.parameter_bindings:
        if binding.get("kind") == "file" and binding.get("name") in spec.python_param_names:
            file_param_by_node[str(binding["node_id"])] = spec.python_param_names[binding["name"]]

    # Detect DbFileInput/DbFileOutput nodes whose original XML <File> was a %User.*% token
    raw_xml_files: dict[str, str] = {}
    if source_wf.source_xml:
        from xml.etree import ElementTree as ET

        try:
            xml_root = ET.fromstring(source_wf.source_xml)
            for el in xml_root.iter("Node"):
                tid = el.get("ToolID")
                f_text = el.findtext("Properties/Configuration/File")
                if tid and f_text:
                    raw_xml_files[tid] = f_text.strip()
        except ET.ParseError:
            pass
    for nid, f_text in raw_xml_files.items():
        m_user = re.fullmatch(r"%User\.([^%|]+)%(\|\|\|.*)?", f_text, flags=re.IGNORECASE)
        if m_user:
            u_key = f"User.{m_user.group(1)}"
            if u_key in spec.python_param_names and nid not in file_param_by_node:
                file_param_by_node[nid] = spec.python_param_names[u_key]

    used_inputs: set[str] = set()
    used_outputs: set[str] = set()
    used_refs: set[str] = set()

    # 3. Extract I/O & Reference nodes
    for node in workflow.nodes:
        cfg = node.config.get("normalized", node.config)
        kind = node.tool_type

        if kind == "DbFileInput":
            file_val = str(cfg.get("file", ""))
            if not file_val:
                raise UnsupportedLowering("DbFileInput config requires file")
            raw, selector = _split_alteryx_file_reference(file_val)
            suffix = _pure_path(raw).suffix.lower()
            file_fmt = _file_attribute(cfg, "FileFormat")
            if suffix == ".yxdb" or file_fmt == "19":
                raise UnsupportedLowering("YXDB input is not supported in Phase 2 native packages")
            is_csv = file_fmt == "0" or suffix in {".csv", ".tsv", ".txt", ".data"}
            is_excel = not is_csv and (file_fmt == "25" or suffix in {".xlsx", ".xls"})
            if not is_csv and not is_excel:
                raise UnsupportedLowering(f"Unsupported DbFileInput FileFormat: {file_fmt or suffix}")

            is_param_bound = node.node_id in file_param_by_node
            portable = (
                _pure_path(raw).name
                if is_param_bound and _pure_path(raw).is_absolute()
                else _portable_relative_path(
                    raw,
                    cfg.get("base_dir"),
                    explicit_binding=bool(cfg.get("explicit_input_binding")),
                )
            )
            stem = _node_annotation(node) or _pure_path(raw).stem or f"input_{node.node_id}"
            key = _unique_key(stem, used_inputs, "source")
            spec.input_key_by_node[node.node_id] = key

            has_header = _header_row(cfg)
            skiprows = max(_import_line(cfg) - 1, 0)
            limit = _record_limit(cfg)
            entry: dict[str, Any] = {
                "path": portable,
                "format": "csv" if is_csv else "excel",
                "has_header": bool(has_header),
                "skip_rows": int(skiprows),
            }
            if limit is not None:
                entry["max_rows"] = int(limit)
            if node.node_id in file_param_by_node:
                if selector:
                    raise UnsupportedLowering("File parameters with worksheet/range selectors require a binding template")
                entry["parameter"] = file_param_by_node[node.node_id]
                entry["expected_suffix"] = suffix
            if is_csv:
                entry["delimiter"] = input_delimiter(cfg)
                enc = input_encoding(cfg)
                if enc:
                    entry["encoding"] = enc
            else:
                excel_opts = excel_selection_options(
                    selector,
                    {"skiprows": skiprows, "nrows": limit, "header": 0 if has_header else None},
                )
                if "sheet_name" in excel_opts and excel_opts["sheet_name"] is not None:
                    entry["sheet_name"] = excel_opts["sheet_name"]
                if "usecols" in excel_opts and excel_opts["usecols"] is not None:
                    entry["usecols"] = excel_opts["usecols"]
                if "skiprows" in excel_opts:
                    entry["skip_rows"] = int(excel_opts["skiprows"])
                if excel_opts.get("nrows") is not None:
                    entry["max_rows"] = int(excel_opts["nrows"])
            spec.inputs[key] = entry

        elif kind == "TextInput":
            fields_list = [str(f) for f in cfg.get("fields", [])]
            rows = cfg.get("rows", [])
            if not fields_list or len(set(fields_list)) != len(fields_list):
                raise UnsupportedLowering("TextInput requires nonempty, unique fields")
            if not isinstance(rows, list):
                raise UnsupportedLowering("TextInput config requires rows to be a list")

            # Check if any cell is bound dynamically to a Question parameter
            cell_params = {
                (int(b["path"][1]), int(b["path"][2])): spec.python_param_names[b["name"]]
                for b in opt.parameter_bindings
                if b.get("kind") == "cell" and str(b.get("node_id")) == node.node_id and b.get("name") in spec.python_param_names
            }
            normalized = [_normalize_row(r, fields_list) for r in rows]
            inferred = _infer_types(pd.DataFrame(normalized, columns=fields_list, dtype=object))

            stem = _node_annotation(node) or f"reference_{node.node_id}"
            key = _unique_key(stem, used_refs, "reference")
            spec.reference_key_by_node[node.node_id] = key
            rel_csv = f"references/{key}.csv"

            buf = io.StringIO(newline="")
            writer = csv.writer(buf, lineterminator="\n")
            writer.writerow(fields_list)
            for row_vals in normalized:
                writer.writerow(["" if v is None else str(v) for v in row_vals])
            spec.reference_files[rel_csv] = buf.getvalue()

            dtypes_map = {col: str(inferred[col].dtype) for col in fields_list}
            null_Sentinels: dict[str, list[int]] = {}
            for c_idx, col in enumerate(fields_list):
                null_rows = [r_idx for r_idx, r in enumerate(normalized) if r[c_idx] is None]
                if null_rows:
                    null_Sentinels[col] = null_rows

            ref_entry: dict[str, Any] = {
                "path": rel_csv,
                "columns": fields_list,
                "dtypes": dtypes_map,
            }
            if null_Sentinels:
                ref_entry["null_rows"] = {k: v for k, v in null_Sentinels.items()}
            if cell_params:
                ref_entry["cell_parameters"] = {f"{r}:{c}": p for (r, c), p in cell_params.items()}
            spec.references[key] = ref_entry

        elif kind == "DbFileOutput":
            file_val = str(cfg.get("file", ""))
            if not file_val:
                raise UnsupportedLowering("DbFileOutput config requires file")
            raw, selector = _split_alteryx_file_reference(file_val)
            p = _pure_path(raw)
            suffix = p.suffix.lower()
            file_fmt = _file_attribute(cfg, "FileFormat")
            stem = _node_annotation(node) or p.stem or f"output_{node.node_id}"
            key = _unique_key(stem, used_outputs, "output")
            spec.output_key_by_node[node.node_id] = key

            limit = _max_records(cfg)
            if suffix == ".xlsx" and file_fmt != "0":
                if node.node_id in file_param_by_node:
                    raise UnsupportedLowering("Parameterized Excel output needs a verified binding")
                sheet, header = xlsx_output_options(cfg, selector)
                out_entry: dict[str, Any] = {
                    "path": p.as_posix(),
                    "filename": p.name,
                    "format": "excel",
                    "sheet_name": sheet,
                    "has_header": bool(header),
                }
            elif file_fmt == "0" or suffix in {".csv", ".eml", ".txt", ".tsv"}:
                if not p.name:
                    raise UnsupportedLowering("DbFileOutput requires a filename")
                has_header = _format_option(cfg, "HeaderRow", "True").lower() == "true"
                delim = _format_option(cfg, "Delimeter", ",") or ","
                ending = _line_ending(cfg)
                code_page = _format_option(cfg, "CodePage", "28591")
                encoding = {"65001": "utf-8", "1200": "utf-16", "28591": "latin-1"}.get(code_page, f"cp{code_page}")
                out_entry = {
                    "path": p.as_posix(),
                    "filename": p.name,
                    "format": "csv",
                    "delimiter": delim,
                    "encoding": encoding,
                    "has_header": bool(has_header),
                    "line_terminator": ending,
                }
                if node.node_id in alteryx_csv_outputs:
                    out_entry["alteryx_Compat_format"] = True
            else:
                if file_fmt == "25" or suffix in {".xlsx", ".xls"}:
                    raise UnsupportedLowering("Excel output is not supported by DbFileOutput for this FileFormat")
                raise UnsupportedLowering(f"Unsupported DbFileOutput FileFormat: {file_fmt or suffix}")

            if limit is not None:
                out_entry["max_rows"] = int(limit)
            if node.node_id in file_param_by_node:
                out_entry["parameter"] = file_param_by_node[node.node_id]
                out_entry["expected_suffix"] = suffix
            spec.outputs[key] = out_entry

        elif kind == "PortfolioComposerRender":
            if delivery_profile == delivery_tools.XLSX_PROFILE:
                try:
                    filename, field_name, group, modifier = delivery_tools.xlsx_render_options(cfg)
                except NotImplementedError as exc:
                    raise UnsupportedLowering(str(exc)) from exc
                configured = cfg.get("output_file") or filename
                key = _unique_key(_pure_path(configured).stem or "report_xlsx", used_outputs, "report")
                spec.output_key_by_node[node.node_id] = key
                spec.outputs[key] = {
                    "path": str(configured),
                    "filename": _pure_path(str(configured)).name,
                    "format": "render_xlsx",
                    "field": field_name,
                    "group_field": group or "",
                    "modifier": modifier or "",
                }
            elif delivery_profile in {delivery_tools.PROFILE, delivery_tools.SMTP_PROFILE}:
                try:
                    filename = delivery_tools.html_render_filename(cfg)
                except NotImplementedError as exc:
                    raise UnsupportedLowering(str(exc)) from exc
                key = _unique_key(_pure_path(filename).stem or "report_html", used_outputs, "report")
                spec.output_key_by_node[node.node_id] = key
                spec.outputs[key] = {
                    "path": filename,
                    "filename": _pure_path(filename).name,
                    "format": "render_html",
                    "data_field": cfg.get("data_field") or "Report",
                }
            else:
                raise UnsupportedLowering("PortfolioComposerRender requires html-draft-v1, html-smtp-v1, or xlsx-table-v1 profile")

        elif kind == "Email":
            if delivery_profile not in {delivery_tools.PROFILE, delivery_tools.SMTP_PROFILE}:
                raise UnsupportedLowering("Email requires explicit html-draft-v1 or html-smtp-v1 profile")
            if cfg.get("unsupported_options"):
                raise UnsupportedLowering(f"Email configuration needs a template: {cfg['unsupported_options']}")
            key = _unique_key(f"email_{node.node_id}", used_outputs, "email")
            spec.output_key_by_node[node.node_id] = key
            spec.outputs[key] = {
                "path": f"email-{node.node_id}.eml" if delivery_profile == delivery_tools.PROFILE else "",
                "filename": f"email-{node.node_id}.eml" if delivery_profile == delivery_tools.PROFILE else "",
                "format": "email_smtp" if delivery_profile == delivery_tools.SMTP_PROFILE else "email_draft",
                "sender": str(cfg.get("from", "")),
                "recipient": str(cfg.get("to", "")),
                "subject": str(cfg.get("subject", "")),
                "body_field": str(cfg.get("body") or "Report"),
                "attachments": [Path(v).name for v in cfg.get("attachments", [])],
            }

    # 4. Extract Workflow Events into [[events.hooks]]
    if source_wf.source_xml:
        try:
            raw_events = bind_logging_events(workflow_events(source_wf.source_xml), log_event_ids)
        except (ValueError, NotImplementedError) as exc:
            raise UnsupportedLowering(str(exc)) from exc
        event_consts = workflow.metadata.get("workflow_constants", {})
        sink_bindings = attachment_bindings(workflow, redirect_sinks=True)

        from alteryx2python.runtime.variables import TOKEN, resolve_variable_tokens

        def template_event_str(raw_val: str) -> str:
            pieces: list[str] = []
            pos = 0
            for m in TOKEN.finditer(raw_val):
                ns, name = m.group(1), m.group(2)
                full = f"{ns}.{name}" if ns else name
                if full in spec.python_param_names:
                    pieces.append(resolve_variable_tokens(raw_val[pos : m.start()], event_consts))
                    pieces.append("{" + spec.python_param_names[full] + "}")
                    pos = m.end()
            pieces.append(resolve_variable_tokens(raw_val[pos:], event_consts))
            return "".join(pieces)

        for ev in raw_events:
            ev_kind = ev.get("kind", "command")
            if ev_kind == "logging":
                spec.events.append({
                    "id": str(ev["id"]),
                    "when": str(ev["when"]),
                    "kind": "logging",
                    "workflow_name": Path(source_wf.source_file).stem if source_wf.source_file else "workflow",
                })
            elif ev_kind == "email":
                if delivery_profile not in {delivery_tools.PROFILE, delivery_tools.SMTP_PROFILE}:
                    raise UnsupportedLowering("Email events require an explicit html-draft-v1 or html-smtp-v1 profile")
                if ev.get("dcm") and delivery_profile == delivery_tools.SMTP_PROFILE:
                    raise UnsupportedLowering("Email event DCM connection needs an explicit SMTP adapter")
                att_specs: list[str] = []
                for item in ev.get("attachments", []):
                    resolved = resolve_variable_tokens(item, event_consts)
                    produced = attachment_output(resolved, sink_bindings)
                    att_specs.append(f"output:{produced}" if produced else template_event_str(item))
                spec.events.append({
                    "id": str(ev["id"]),
                    "when": str(ev["when"]),
                    "kind": "email_smtp" if delivery_profile == delivery_tools.SMTP_PROFILE else "email_draft",
                    "sender": template_event_str(ev["sender"]),
                    "recipient": template_event_str(ev["recipient"]),
                    "subject": template_event_str(ev["subject"]),
                    "body": template_event_str(ev["body"]),
                    "attachments": att_specs,
                    "draft_filename": f"event-{ev['id']}.eml" if delivery_profile == delivery_tools.PROFILE else "",
                    "host": template_event_str(ev["host"]),
                    "port": template_event_str(str(ev["port"])),
                    "security": template_event_str(ev["security"]),
                    "authentication": bool(ev["authentication"]),
                    "username": template_event_str(ev["username"]),
                })
            else:
                spec.events.append({
                    "id": str(ev["id"]),
                    "when": str(ev["when"]),
                    "kind": "command",
                    "program": template_event_str(ev["program"]),
                    "arguments": template_event_str(ev["arguments"]),
                    "working_dir": template_event_str(ev["working_dir"]),
                    "timeout": int(ev["timeout"]),
                })

    return spec

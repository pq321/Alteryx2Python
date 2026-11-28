"""Clean, framework-free Python module templates for Phase 2 generated packages."""

from __future__ import annotations

import textwrap
from pprint import pformat
from typing import Any

from alteryx2python.generator.config_extractor import ConfigSpec
from alteryx2python.generator.source_linker import SourceLinker
from alteryx2python.parser.tool_parsers.textinput_parser import normalize_cell_text
from alteryx2python.tools.textinput import _infer_types


def render_init_py() -> str:
    return '"""Generated native Python data pipeline package."""\n\nfrom .pipeline import transform\nfrom .runner import run_pipeline\n\n__all__ = ["transform", "run_pipeline"]\n'


def render_runner_py(spec: ConfigSpec, io_helpers: list[str], operation_helpers: dict[str, str]) -> str:
    imports = ["from functools import partial", "from pathlib import Path"] if spec.operations or "file_exists" in operation_helpers else []
    relative = ["from .audit_utils import create_audit_logger", "from .pipeline import _transform"]
    if io_helpers:
        relative.append(f"from .io_utils import {', '.join(io_helpers)}")
    if "render_xlsx" in operation_helpers:
        relative.append("from .io_utils import resolve_output_path")
    if operation_helpers:
        relative.append(f"from .helpers import {', '.join(operation_helpers.values())}")
    imports.extend(["if __package__:", *[f"    {line}" for line in relative], "else:"])
    imports.extend(f"    {line.replace('from .', 'from ', 1)}" for line in relative)

    blocks = ["\n".join(imports)]
    if "directory" in operation_helpers:
        blocks.append(textwrap.dedent(f"""
            def _list_directory(entry, input_dir):
                directory = (input_dir / entry["directory"]).resolve()
                return {operation_helpers['directory']}(directory, entry["file_spec"], entry["include_subdirs"])
        """).strip())
    if "dynamic" in operation_helpers:
        blocks.append(textwrap.dedent(f"""
            def _read_dynamic(entry, input_dir, parameters, frame, field):
                template = parameters.get(entry.get("parameter"), entry["template"])
                if Path(template.partition("|||")[0]).suffix.lower() != entry["expected_suffix"]:
                    raise ValueError("Dynamic Input template must keep its configured file format")
                options = {{"header": None, "nrows": None, **entry["read_options"]}}
                return {operation_helpers['dynamic']}(
                    frame, field, template, options, entry.get("input_dir", input_dir), entry["behaviour"],
                    action=entry["action"], path_aliases=entry.get("path_aliases"),
                    schema_reference=entry.get("schema_reference"),
                )
        """).strip())
    if "file_exists" in operation_helpers:
        blocks.append(textwrap.dedent(f"""
            def _file_exists(runtime, value):
                aliases = runtime.get("input_aliases")
                if aliases and isinstance(value, str) and value:
                    original = Path(runtime["original_input_dir"]) / value
                    value = aliases.get(str(original.resolve()), value)
                return {operation_helpers['file_exists']}(value)
        """).strip())
    if "command" in operation_helpers:
        blocks.append(textwrap.dedent(f"""
            def _run_command(entry, runtime, input_dir, frame, **overrides):
                entry = {{**entry, **overrides}}
                program = entry["program_name"]
                if not Path(program).is_absolute() and (input_dir / program).is_file():
                    program = str((input_dir / program).resolve())
                work_dir = Path(runtime["command_working_dir"]) if runtime.get("command_working_dir") else input_dir / entry["working_dir"]
                return {operation_helpers['command']}(
                    program, entry["arguments"], work_dir, frame, entry["input_file"],
                    entry["output_file"], runtime.get("allowed_commands", ()),
                )
        """).strip())

    lines = [
        "def run_pipeline(config):",
        '    runtime = config.get("runtime", {})',
        '    parameters = config.get("parameters", {})',
        "    audit = create_audit_logger(config)",
        "    written_outputs = {}",
        "    operations = {}",
    ]
    if spec.operations:
        lines.append('    input_dir = Path(runtime.get("input_dir", "."))')
        for key in spec.operations:
            if key.startswith("directory_"):
                call = "_list_directory, entry, input_dir"
            elif key.startswith("dynamic_input_"):
                call = "_read_dynamic, entry, input_dir, parameters"
            else:
                call = "_run_command, entry, runtime, input_dir"
            lines.extend([
                f'    entry = config["operations"][{key!r}]',
                f"    operations[{key!r}] = partial({call})",
            ])
    if "file_exists" in operation_helpers:
        lines.append('    operations["file_exists"] = partial(_file_exists, runtime)')
    lines.extend(["", "    def read_table(section, key, label):"])
    for section, reader in (("inputs", "read_input_table"), ("references", "read_reference_table")):
        if reader in io_helpers:
            lines.extend([
                f"        if section == {section!r}:",
                f"            return {reader}(config, key, audit=audit, tool_label=label)",
            ])
    lines.append("        raise KeyError((section, key))")
    sink = ""
    if "write_output_table" in io_helpers:
        lines.extend(["", "    def write_result(frame, key, label):"])
        if "render_xlsx" in operation_helpers:
            lines.extend([
                '        entry = config["outputs"][key]',
                '        if entry["format"] == "render_xlsx":',
                '            destination = resolve_output_path(config, entry)',
                f"            written_outputs[key] = {operation_helpers['render_xlsx']}(",
                '                frame, destination, entry["field"], entry["group_field"] or None, entry["modifier"] or None,',
                '            )',
                '            return',
            ])
        lines.append("        written_outputs[key] = write_output_table(frame, config, key, audit=audit, tool_label=label)")
        sink = ", write_result=write_result"
    lines.extend([
        "",
        "    audit.start_pipeline(parameters=parameters)",
        "    try:",
        f"        result = _transform(read_table, parameters, operations, run_stage=audit.run_stage, audit=audit{sink})",
        "    except Exception as exc:",
        "        audit.fail_pipeline(exc)",
        "        raise",
        "    else:",
        "        audit.finish_pipeline(outputs=written_outputs)",
        "    finally:",
        "        audit.close()",
        '    return {"output_dir": str(runtime.get("output_dir", "output")), "outputs": written_outputs,',
        '            "frames": result if not written_outputs else {}, "audit": audit.records}',
    ])
    return "\n\n\n".join([*blocks, "\n".join(lines)]) + "\n"


def render_main_py() -> str:
    return textwrap.dedent(
        '''
        """Allow both `python -m <package>` and `python -I <package_dir>` execution."""

        from pathlib import Path
        import sys

        if __package__:
            from .cli import main
        else:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from cli import main

        if __name__ == "__main__":
            raise SystemExit(main())
        '''
    ).lstrip()


def render_audit_utils_py(stage_audit: dict[str, tuple[str, str]]) -> str:
    """Emit a framework-free stdlib logging module for step-by-step pipeline auditing."""
    return textwrap.dedent(
        '''
        """Step-by-step pipeline auditing utilities backed by Python stdlib logging."""

        from __future__ import annotations

        from datetime import datetime, timezone
        import json
        import logging
        from pathlib import Path
        import sys
        import time
        from uuid import uuid4

        import pandas as pd

        PACKAGE_DIR = Path(__file__).resolve().parent
        _SENSITIVE_KEYS = ("password", "secret", "token", "api_key", "apikey", "credential")
        _LEVEL_MAP = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "WARN": logging.WARNING,
            "ERROR": logging.ERROR,
        }


        __STAGE_AUDIT__


        def _redact_params(params: dict | None) -> dict:
            if not params:
                return {}
            redacted: dict = {}
            for key, val in params.items():
                low = str(key).lower()
                redacted[str(key)] = "***REDACTED***" if any(part in low for part in _SENSITIVE_KEYS) else val
            return redacted


        def _frame_shape(frame: pd.DataFrame) -> dict:
            return {
                "rows": int(len(frame)),
                "cols": int(len(frame.columns)),
                "columns": [str(col) for col in frame.columns],
            }


        def _extract_frames(value: object) -> list[pd.DataFrame]:
            if isinstance(value, pd.DataFrame):
                return [value]
            if isinstance(value, (tuple, list)):
                return [item for item in value if isinstance(item, pd.DataFrame)]
            if isinstance(value, dict):
                return [item for item in value.values() if isinstance(item, pd.DataFrame)]
            return []


        class _AuditFormatter(logging.Formatter):
            def __init__(self, fmt_mode: str) -> None:
                super().__init__()
                self.fmt_mode = fmt_mode

            def format(self, record: logging.LogRecord) -> str:
                payload = getattr(record, "audit_payload", None)
                if self.fmt_mode == "jsonl" and isinstance(payload, dict):
                    return json.dumps(payload, ensure_ascii=False, default=str)
                ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
                return f"[{ts}] {record.levelname:<5} {record.getMessage()}"


        class AuditLogger:
            """Structured and human-readable step auditor for migrated data pipelines."""

            def __init__(
                self,
                *,
                enabled: bool = True,
                level: str = "INFO",
                fmt_mode: str = "text",
                log_file: str | Path | None = None,
                scope: str | None = None,
            ) -> None:
                self.run_id = uuid4().hex[:8]
                self.scope = scope
                self.records: list[dict] = []
                self._step_counter = 0
                self._started_perf = time.perf_counter()
                norm_level = str(level or "INFO").strip().upper()
                self.enabled = bool(enabled) and norm_level != "OFF"
                self._handlers: list[logging.Handler] = []
                self._logger = logging.getLogger(f"pipeline.audit.{self.run_id}" + (f".{scope}" if scope else ""))
                self._logger.propagate = False
                self._logger.handlers.clear()

                if self.enabled:
                    py_level = _LEVEL_MAP.get(norm_level, logging.INFO)
                    self._logger.setLevel(py_level)
                    stream_handler = logging.StreamHandler(sys.stderr)
                    stream_handler.setLevel(py_level)
                    stream_handler.setFormatter(_AuditFormatter(fmt_mode))
                    self._logger.addHandler(stream_handler)
                    self._handlers.append(stream_handler)

                    if log_file:
                        file_path = Path(log_file)
                        if not file_path.is_absolute():
                            file_path = (PACKAGE_DIR / file_path).resolve()
                        file_path.parent.mkdir(parents=True, exist_ok=True)
                        file_fmt = "jsonl" if file_path.suffix.lower() == ".jsonl" and fmt_mode == "text" else fmt_mode
                        file_handler = logging.FileHandler(file_path, encoding="utf-8")
                        file_handler.setLevel(py_level)
                        file_handler.setFormatter(_AuditFormatter(file_fmt))
                        self._logger.addHandler(file_handler)
                        self._handlers.append(file_handler)

            def _emit(self, py_level: int, text_msg: str, payload: dict) -> None:
                self.records.append(payload)
                if self.enabled:
                    prefix = f"[run={self.run_id}" + (f" scope={self.scope}] " if self.scope else "] ")
                    self._logger.log(py_level, prefix + text_msg, extra={"audit_payload": payload})

            def close(self) -> None:
                for handler in list(self._handlers):
                    self._logger.removeHandler(handler)
                    try:
                        handler.flush()
                        handler.close()
                    except OSError:
                        pass
                self._handlers.clear()

            def start_pipeline(self, *, parameters: dict | None = None) -> None:
                self._started_perf = time.perf_counter()
                safe_params = _redact_params(parameters)
                payload = {
                    "run_id": self.run_id,
                    "scope": self.scope,
                    "kind": "pipeline_start",
                    "status": "started",
                    "parameters": safe_params,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                param_text = f" | params={safe_params}" if safe_params else ""
                lvl = logging.DEBUG if self.scope else logging.INFO
                self._emit(lvl, f"START pipeline{param_text}", payload)

            def record_io(
                self,
                kind: str,
                key: str,
                tool_label: str,
                df: pd.DataFrame,
                path: Path | str | None,
                duration_ms: float,
            ) -> None:
                self._step_counter += 1
                shape = _frame_shape(df)
                artifact_name = Path(path).name if path else key
                direction = "<-" if kind in {"input", "reference"} else "->"
                col_preview = shape["columns"][:6]
                col_str = "[" + ", ".join(col_preview) + (", ..." if len(shape["columns"]) > 6 else "") + "]"
                tool_part = f" ({tool_label})" if tool_label else ""
                payload = {
                    "run_id": self.run_id,
                    "scope": self.scope,
                    "step_index": self._step_counter,
                    "kind": kind,
                    "step": key,
                    "tool": tool_label,
                    "status": "ok",
                    "rows": shape["rows"],
                    "cols": shape["cols"],
                    "columns": shape["columns"],
                    "artifact": artifact_name,
                    "artifact_path": str(path) if path else None,
                    "duration_ms": round(duration_ms, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                lvl = logging.DEBUG if self.scope else logging.INFO
                self._emit(
                    lvl,
                    f"[Step {self._step_counter}] {kind.upper()} {key}{tool_part} | {shape['rows']} rows x {shape['cols']} cols {col_str} {direction} {artifact_name} ({duration_ms:.2f} ms)",
                    payload,
                )

            def run_stage(self, func, /, *args, **kwargs):
                name = func.__name__
                label, description = _STAGE_AUDIT[name]
                return self.run_step(name, label, description, func, *args, **kwargs)

            def skip_stage(self, func):
                name = func.__name__
                label, description = _STAGE_AUDIT[name]
                self.skip_step(name, label, description)

            def run_step(self, step_name: str, tool_label: str, description: str, func, /, *args, **kwargs):
                self._step_counter += 1
                step_idx = self._step_counter
                in_frames = [arg for arg in args if isinstance(arg, pd.DataFrame)]
                in_shapes = [_frame_shape(f) for f in in_frames]
                step_params = _redact_params({k: v for k, v in kwargs.items() if k != "config" and not isinstance(v, pd.DataFrame)})
                t0 = time.perf_counter()
                try:
                    result = func(*args, **kwargs)
                except Exception as exc:
                    elapsed_ms = (time.perf_counter() - t0) * 1000.0
                    err_payload = {
                        "run_id": self.run_id,
                        "scope": self.scope,
                        "step_index": step_idx,
                        "kind": "transform",
                        "step": step_name,
                        "tool": tool_label,
                        "summary": description,
                        "status": "failed",
                        "inputs": in_shapes,
                        "parameters": step_params,
                        "error_type": type(exc).__name__,
                        "error": str(exc),
                        "duration_ms": round(elapsed_ms, 2),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    self._emit(
                        logging.ERROR,
                        f"[Step {step_idx}] FAIL {step_name} ({tool_label}) | {description} | {type(exc).__name__}: {exc} ({elapsed_ms:.2f} ms)",
                        err_payload,
                    )
                    raise

                elapsed_ms = (time.perf_counter() - t0) * 1000.0
                out_frames = _extract_frames(result)
                out_shapes = [_frame_shape(f) for f in out_frames]

                row_delta: int | None = None
                cols_added: list[str] = []
                cols_removed: list[str] = []
                if len(in_shapes) == 1 and len(out_shapes) == 1:
                    row_delta = out_shapes[0]["rows"] - in_shapes[0]["rows"]
                    in_col_set = set(in_shapes[0]["columns"])
                    out_col_set = set(out_shapes[0]["columns"])
                    cols_added = [c for c in out_shapes[0]["columns"] if c not in in_col_set]
                    cols_removed = [c for c in in_shapes[0]["columns"] if c not in out_col_set]
                    details = [f"rows {row_delta:+d}"]
                    if cols_added:
                        details.append(f"+cols={cols_added[:5]}" + ("..." if len(cols_added) > 5 else ""))
                    if cols_removed:
                        details.append(f"-cols={cols_removed[:5]}" + ("..." if len(cols_removed) > 5 else ""))
                    shape_msg = f"{in_shapes[0]['rows']}x{in_shapes[0]['cols']} -> {out_shapes[0]['rows']}x{out_shapes[0]['cols']} ({', '.join(details)})"
                else:
                    in_str = "[" + ", ".join(f"{s['rows']}x{s['cols']}" for s in in_shapes) + "]" if in_shapes else "0"
                    out_str = (
                        f"{out_shapes[0]['rows']}x{out_shapes[0]['cols']}"
                        if len(out_shapes) == 1
                        else "[" + ", ".join(f"{s['rows']}x{s['cols']}" for s in out_shapes) + "]"
                    )
                    shape_msg = f"{in_str} -> {out_str}"

                payload = {
                    "run_id": self.run_id,
                    "scope": self.scope,
                    "step_index": step_idx,
                    "kind": "transform",
                    "step": step_name,
                    "tool": tool_label,
                    "summary": description,
                    "status": "ok",
                    "inputs": in_shapes,
                    "outputs": out_shapes,
                    "row_delta": row_delta,
                    "columns_added": cols_added,
                    "columns_removed": cols_removed,
                    "parameters": step_params,
                    "duration_ms": round(elapsed_ms, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                lvl = logging.DEBUG if self.scope else logging.INFO
                self._emit(
                    lvl,
                    f"[Step {step_idx}] STEP {step_name} ({tool_label}) | {description} | {shape_msg} ({elapsed_ms:.2f} ms)",
                    payload,
                )
                return result

            def skip_step(
                self,
                step_name: str,
                tool_label: str,
                description: str,
                *,
                reason: str = "guard_condition_false",
            ) -> None:
                self._step_counter += 1
                payload = {
                    "run_id": self.run_id,
                    "scope": self.scope,
                    "step_index": self._step_counter,
                    "kind": "skip",
                    "step": step_name,
                    "tool": tool_label,
                    "summary": description,
                    "status": "skipped",
                    "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                lvl = logging.DEBUG if self.scope else logging.INFO
                self._emit(
                    lvl,
                    f"[Step {self._step_counter}] SKIP {step_name} ({tool_label}) | {description} | reason={reason}",
                    payload,
                )

            def finish_pipeline(self, *, outputs: dict | None = None) -> None:
                total_ms = (time.perf_counter() - self._started_perf) * 1000.0
                out_names = {k: Path(v).name if isinstance(v, (Path, str)) else str(v) for k, v in (outputs or {}).items()}
                payload = {
                    "run_id": self.run_id,
                    "scope": self.scope,
                    "kind": "pipeline_end",
                    "status": "completed",
                    "steps_executed": self._step_counter,
                    "outputs": out_names,
                    "duration_ms": round(total_ms, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                lvl = logging.DEBUG if self.scope else logging.INFO
                self._emit(
                    lvl,
                    f"DONE pipeline | steps={self._step_counter} | outputs={len(out_names)} | total={total_ms:.2f} ms",
                    payload,
                )
                self.close()

            def fail_pipeline(self, error: BaseException) -> None:
                total_ms = (time.perf_counter() - self._started_perf) * 1000.0
                payload = {
                    "run_id": self.run_id,
                    "scope": self.scope,
                    "kind": "pipeline_end",
                    "status": "failed",
                    "steps_executed": self._step_counter,
                    "error_type": type(error).__name__,
                    "error": str(error),
                    "duration_ms": round(total_ms, 2),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                self._emit(
                    logging.ERROR,
                    f"FAIL pipeline | steps={self._step_counter} | {type(error).__name__}: {error} | total={total_ms:.2f} ms",
                    payload,
                )
                self.close()


        def create_audit_logger(config: dict | None = None, *, scope: str | None = None) -> AuditLogger:
            log_cfg = (config or {}).get("logging") or {}
            return AuditLogger(
                enabled=bool(log_cfg.get("enabled", True)),
                level=str(log_cfg.get("level", "INFO")),
                fmt_mode=str(log_cfg.get("format", "text")).strip().lower() or "text",
                log_file=log_cfg.get("file") or None,
                scope=scope,
            )
        '''
    ).lstrip().replace("__STAGE_AUDIT__", "_STAGE_AUDIT = " + pformat(stage_audit))


def render_io_utils_py(
    spec: ConfigSpec,
    *,
    needs_excel_in: bool = False,
    needs_excel_out: bool = False,
    needs_render_html: bool = False,
    needs_render_xlsx: bool = False,
    needs_email: bool = False,
    needs_commands: bool = False,
    needs_events: bool = False,
) -> str:
    """Emit a concise, native Python io_utils.py tailored to the features actually used."""
    imports = [
        "from __future__ import annotations",
        "import codecs",
        "from copy import deepcopy",
        "import json",
        "import os",
        "from pathlib import Path, PureWindowsPath",
        "import time",
        "import tomllib",
        "import pandas as pd",
    ]
    if needs_events:
        imports.append("from contextlib import contextmanager")
        imports.append("import warnings")
    if needs_commands or any(e.get("kind") == "command" for e in spec.events):
        imports.extend(["import shlex", "import subprocess"])
    if needs_email or any(str(e.get("kind", "")).startswith("email") for e in spec.events):
        imports.extend([
            "from email.message import EmailMessage",
            "import mimetypes",
            "import smtplib",
            "import ssl",
        ])
    if any(e.get("kind") == "logging" for e in spec.events):
        imports.extend([
            "import csv",
            "from datetime import datetime, timezone",
            "import io",
            "import logging",
            "import socket",
            "from uuid import uuid4",
        ])

    reference_linker = SourceLinker()
    restore_reference_types = "out_df = _restore_reference_types(df, entry)"
    if any(entry.get("cell_parameters") for entry in spec.references.values()):
        infer_types = reference_linker.function(_infer_types)
        cell_text = reference_linker.function(normalize_cell_text)
        imports.extend(reference_linker.imports)
        restore_reference_types = textwrap.dedent(f'''
            cell_params = entry.get("cell_parameters")
            if cell_params:
                params = config.get("parameters", {{}})
                for coord, param_name in cell_params.items():
                    row, col = map(int, coord.split(":", 1))
                    if param_name in params:
                        df.iat[row, col] = {cell_text}(params[param_name])
                out_df = {infer_types}(df)
            else:
                out_df = _restore_reference_types(df, entry)
        ''').strip()

    sections: list[str] = ['"""Configuration loading and native table I/O utilities."""\n\n' + "\n".join(sorted(set(imports)))]
    sections.extend(reference_linker.definitions.values())

    sections.append(
        textwrap.dedent(
            '''
            PACKAGE_DIR = Path(__file__).resolve().parent


            def _deep_merge(base: dict, override: dict) -> dict:
                merged = deepcopy(base)
                for key, value in override.items():
                    if isinstance(value, dict) and isinstance(merged.get(key), dict):
                        merged[key] = _deep_merge(merged[key], value)
                    else:
                        merged[key] = deepcopy(value)
                return merged


            def _parse_config_file(path: Path) -> dict:
                raw = path.read_bytes()
                if path.suffix.lower() == ".json":
                    return json.loads(raw.decode("utf-8-sig"))
                return tomllib.loads(raw.decode("utf-8-sig"))


            def load_config(
                config_path: str | Path | None = None,
                *,
                overrides: dict | None = None,
                input_dir: str | Path | None = None,
                output_dir: str | Path | None = None,
                use_workflow_output_paths: bool = False,
            ) -> dict:
                if use_workflow_output_paths and output_dir is not None:
                    raise ValueError("Choose workflow output paths or an isolated output directory")
                default_toml = PACKAGE_DIR / "config.toml"
                config = _parse_config_file(default_toml) if default_toml.is_file() else {
                    "inputs": {}, "outputs": {}, "parameters": {},
                }
                config_dir = PACKAGE_DIR
                if config_path is not None:
                    cfg_file = Path(config_path).resolve()
                    config = _deep_merge(config, _parse_config_file(cfg_file))
                    config_dir = cfg_file.parent
                if overrides:
                    config = _deep_merge(config, overrides)
                runtime = config.setdefault("runtime", {})
                resolved_in = Path(input_dir or runtime.get("input_dir") or config_dir).resolve()
                resolved_out = Path(output_dir or runtime.get("output_dir") or (config_dir / "output")).resolve()
                use_wf_paths = bool(use_workflow_output_paths or runtime.get("use_workflow_output_paths", False))
                runtime["input_dir"] = str(resolved_in)
                runtime["output_dir"] = str(resolved_out)
                runtime["use_workflow_output_paths"] = use_wf_paths
                if not use_wf_paths:
                    resolved_out.mkdir(parents=True, exist_ok=True)
                return config


            def _expand_path_tokens(raw_path: str) -> str:
                if raw_path.lower().startswith("%temp%"):
                    suffix = raw_path[len("%temp%") :].lstrip("\\\\/")
                    return str(Path(os.environ.get("TEMP", ".")) / suffix)
                return raw_path


            def resolve_input_path(config: dict, entry: dict) -> Path:
                input_dir = Path(config.get("runtime", {}).get("input_dir") or PACKAGE_DIR)
                param_key = entry.get("parameter")
                raw = str(config.get("parameters", {}).get(param_key) or entry["path"]) if param_key else str(entry["path"])
                if entry.get("format") == "excel":
                    raw = raw.partition("|||")[0]
                expected_suffix = entry.get("expected_suffix")
                if param_key and expected_suffix and Path(raw).suffix.lower() != str(expected_suffix).lower():
                    raise ValueError(f"Input file parameter {param_key!r} must have {expected_suffix} extension")
                raw = _expand_path_tokens(raw)
                candidate = Path(raw)
                return candidate.resolve() if candidate.is_absolute() else (input_dir / candidate).resolve()


            def resolve_output_path(config: dict, entry: dict) -> Path:
                runtime = config.get("runtime", {})
                input_dir = Path(runtime.get("input_dir") or PACKAGE_DIR)
                output_dir = Path(runtime.get("output_dir") or (PACKAGE_DIR / "output"))
                use_wf_paths = bool(runtime.get("use_workflow_output_paths", False))
                param_key = entry.get("parameter")
                raw = str(config.get("parameters", {}).get(param_key) or entry["path"]) if param_key else str(entry["path"])
                expected_suffix = entry.get("expected_suffix")
                if param_key and expected_suffix and Path(raw).suffix.lower() != str(expected_suffix).lower():
                    raise ValueError(f"Output file parameter {param_key!r} must have {expected_suffix} extension")
                raw = _expand_path_tokens(raw)
                if use_wf_paths:
                    candidate = Path(raw)
                    return candidate.resolve() if candidate.is_absolute() else (input_dir / candidate).resolve()
                filename = PureWindowsPath(raw).name or entry.get("filename") or Path(raw).name
                return (output_dir / filename).resolve()
            '''
        ).strip()
    )

    from alteryx2python.tools.csv_input import read_delimited_file
    from alteryx2python.tools.dbfileinput import read_excel_data
    from alteryx2python.tools.dbfileoutput import write_delimited_table, write_xlsx
    from alteryx2python.yxdb_file import read_yxdb_frame

    io_linker = SourceLinker()
    csv_reader = io_linker.function(read_delimited_file)
    excel_reader = io_linker.function(read_excel_data)
    yxdb_reader = io_linker.function(read_yxdb_frame)
    csv_writer = io_linker.function(write_delimited_table)
    excel_writer = io_linker.function(write_xlsx)
    sections.append(io_linker.render().removeprefix("from __future__ import annotations\n").strip())

    # Delimited & Excel readers
    sections.append(
        textwrap.dedent(
            '''
            def read_input_table(config: dict, key: str, *, audit=None, tool_label: str = "") -> pd.DataFrame:
                t0 = time.perf_counter()
                entry = config["inputs"][key]
                path = resolve_input_path(config, entry)
                fmt = entry.get("format", "csv")
                has_header = bool(entry.get("has_header", True))
                header = 0 if has_header else None
                skiprows = int(entry.get("skip_rows", 0))
                nrows = entry.get("max_rows")

                if fmt == "yxdb":
                    df = _read_yxdb(path, limit=nrows)
                elif fmt == "excel":
                    df = _read_excel(
                        path, header=header, skiprows=skiprows, nrows=nrows,
                        sheet_name=entry.get("sheet_name", 0), usecols=entry.get("usecols"),
                        defined_name=entry.get("defined_name"), sheet_list=entry.get("sheet_list", False),
                    )
                else:
                    df = _read_csv(
                        path, encoding=entry.get("encoding") or None, sep=entry.get("delimiter", ","),
                        header=header, skiprows=skiprows, nrows=nrows,
                    )

                if not has_header and not entry.get("sheet_list"):
                    df.columns = [f"F{idx}" for idx in range(1, len(df.columns) + 1)]
                if audit is not None:
                    audit.record_io("input", key, tool_label, df, path, (time.perf_counter() - t0) * 1000.0)
                return df
            '''
        ).strip()
    )

    if spec.references:
        sections.append(
            textwrap.dedent(
                '''
                def read_reference_table(config: dict, key: str, *, audit=None, tool_label: str = "") -> pd.DataFrame:
                    t0 = time.perf_counter()
                    entry = config["references"][key]
                    rel_path = Path(entry["path"])
                    path = rel_path if rel_path.is_absolute() else (PACKAGE_DIR / rel_path)
                    df = pd.read_csv(path, dtype=object, keep_default_na=False)
                    for col, indices in (entry.get("null_rows") or {}).items():
                        if col in df.columns:
                            df.loc[indices, col] = None
                    __RESTORE_REFERENCE_TYPES__
                    if audit is not None:
                        audit.record_io("reference", key, tool_label, out_df, path, (time.perf_counter() - t0) * 1000.0)
                    return out_df


                def _restore_reference_types(df: pd.DataFrame, entry: dict) -> pd.DataFrame:
                    dtypes = entry.get("dtypes") or {}
                    result: dict[str, pd.Series] = {}
                    for col in entry.get("columns", list(df.columns)):
                        target_dtype = dtypes.get(col, "object")
                        series = df[col]
                        if target_dtype in {"int64", "Int64", "Int32", "Int16", "UInt8"}:
                            num = pd.to_numeric(series.replace("", pd.NA), errors="coerce")
                            result[col] = num.astype("int64" if target_dtype == "int64" and not num.isna().any() else (
                                "Int64" if target_dtype == "int64" else target_dtype
                            ))
                        elif target_dtype in {"float64", "Float64"}:
                            result[col] = pd.to_numeric(series.replace("", pd.NA), errors="coerce").astype("float64")
                        elif target_dtype in {"bool", "boolean"}:
                            mapped = series.map(
                                lambda v: pd.NA if v is None or v == "" else str(v).strip().lower() in {"true", "1"}
                            )
                            result[col] = mapped.astype("boolean" if mapped.isna().any() or target_dtype == "boolean" else "bool")
                        elif target_dtype.startswith("datetime64"):
                            result[col] = pd.to_datetime(series.replace("", pd.NA), errors="coerce").astype(target_dtype)
                        else:
                            result[col] = series.astype(target_dtype)
                    return pd.DataFrame(result)
                '''
            ).strip().replace(
                "    __RESTORE_REFERENCE_TYPES__",
                textwrap.indent(restore_reference_types, "    "),
            )
        )

    # Output writer
    writer_code = textwrap.dedent(
        '''
        def _write_output_impl(out_df: pd.DataFrame, config: dict, entry: dict) -> Path:
            fmt = entry.get("format", "csv")

            if fmt == "excel":
                path = resolve_output_path(config, entry)
                path.parent.mkdir(parents=True, exist_ok=True)
                sheet_name = str(entry.get("sheet_name") or "Sheet1")
                has_header = bool(entry.get("has_header", True))
                _write_excel(
                    path, out_df, sheet_name, header=has_header,
                    replace_sheet=bool(entry.get("replace_sheet")), sheet_index=entry.get("sheet_index"),
                )
                return path
        '''
    ).strip()

    if needs_render_html:
        writer_code += "\n\n" + textwrap.indent(
            textwrap.dedent(
                '''
                if fmt == "render_html":
                    path = resolve_output_path(config, entry)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    data_field = str(entry.get("data_field") or "Report")
                    fragments = [str(v) for v in out_df.get(data_field, pd.Series(dtype=object)) if v is not None and not pd.isna(v)]
                    html_doc = "<!DOCTYPE html><html><head><meta charset=\\"utf-8\\"></head><body>" + "\\n".join(fragments) + "</body></html>"
                    path.write_text(html_doc, encoding="utf-8")
                    return path
                '''
            ).strip(),
            "    ",
        )

    if needs_email:
        writer_code += "\n\n" + textwrap.indent(
            textwrap.dedent(
                '''
                if fmt in {"email_draft", "email_smtp"}:
                    output_dir = Path(config.get("runtime", {}).get("output_dir") or (PACKAGE_DIR / "output"))
                    input_dir = Path(config.get("runtime", {}).get("input_dir") or PACKAGE_DIR)
                    attachments = [
                        output_dir / name[7:] if name.startswith("output:") else input_dir / name
                        for name in entry.get("attachments", [])
                    ]
                    dest = resolve_output_path(config, entry) if fmt == "email_draft" else None
                    if "plain_body" in entry:
                        if len(out_df) != 1:
                            raise ValueError("Email profile requires exactly one message record")
                        _deliver_email_message(
                            str(entry.get("sender", "")), str(entry.get("recipient", "")),
                            str(entry.get("subject", "")), str(entry["plain_body"]),
                            attachments, dest,
                            host=entry.get("smtp_server", ""), port=entry.get("smtp_port", "25"), security="plain",
                        )
                        return dest or output_dir
                    body_field = str(entry.get("body_field") or "Report")
                    fragments = [str(v) for v in out_df.get(body_field, pd.Series(dtype=object)) if v is not None and not pd.isna(v)]
                    html_body = "<html><body>" + "\\n".join(fragments) + "</body></html>"
                    _deliver_email_message(
                        str(entry.get("sender", "")),
                        str(entry.get("recipient", "")),
                        str(entry.get("subject", "")),
                        html_body,
                        attachments,
                        dest,
                        is_html=True,
                    )
                    return dest or output_dir
                '''
            ).strip(),
            "    ",
        )

    writer_code += "\n\n" + textwrap.indent(
        textwrap.dedent(
            '''
            path = resolve_output_path(config, entry)
            path.parent.mkdir(parents=True, exist_ok=True)
            delimiter = str(entry.get("delimiter", ","))
            encoding = str(entry.get("encoding", "utf-8"))
            has_header = bool(entry.get("has_header", True))
            line_terminator = str(entry.get("line_terminator", "\\n"))
            _write_csv(path, out_df, header=has_header, delimiter=delimiter,
                       line_ending=line_terminator, encoding=encoding, midnight_as_date=True)
            return path
            '''
        ).strip(),
        "    ",
    )
    writer_code += "\n\n\n" + textwrap.dedent(
        '''
        def write_output_table(
            df: pd.DataFrame,
            config: dict,
            key: str,
            *,
            audit=None,
            tool_label: str = "",
        ) -> Path:
            t0 = time.perf_counter()
            entry = config["outputs"][key]
            max_rows = entry.get("max_rows")
            out_df = df.head(int(max_rows)) if max_rows is not None else df
            written_path = _write_output_impl(out_df, config, entry)
            if audit is not None:
                audit.record_io("output", key, tool_label, out_df, written_path, (time.perf_counter() - t0) * 1000.0)
            return written_path
        '''
    ).strip()
    sections.append(writer_code)

    if needs_email or any(str(e.get("kind", "")).startswith("email") for e in spec.events):
        sections.append(
            textwrap.dedent(
                '''
                def _deliver_email_message(
                    sender: str,
                    recipient: str,
                    subject: str,
                    body: str,
                    attachments: list[Path],
                    destination: Path | None,
                    *,
                    is_html: bool = False,
                    host: str = "",
                    port: str = "25",
                    security: str = "plain",
                    authentication: bool = False,
                    username: str = "",
                ) -> None:
                    msg = EmailMessage()
                    msg["From"] = sender
                    msg["To"] = recipient
                    msg["Subject"] = subject
                    if is_html:
                        msg.set_content("HTML report attached.")
                        msg.add_alternative(body, subtype="html")
                    else:
                        msg.set_content(body)
                    for att in attachments:
                        if att.is_file():
                            mime, _ = mimetypes.guess_type(str(att))
                            maintype, subtype = (mime or "application/octet-stream").split("/", 1)
                            msg.add_attachment(att.read_bytes(), maintype=maintype, subtype=subtype, filename=att.name)
                    if destination is not None:
                        destination.parent.mkdir(parents=True, exist_ok=True)
                        destination.write_bytes(bytes(msg))
                        return
                    smtp_host = host or os.environ.get("SMTP_HOST", "localhost")
                    smtp_port = int(port or os.environ.get("SMTP_PORT", "25"))
                    smtp_cls = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
                    with smtp_cls(smtp_host, smtp_port, timeout=30) as client:
                        if security == "starttls":
                            client.starttls(context=ssl.create_default_context())
                        if authentication or os.environ.get("SMTP_PASSWORD"):
                            user = username or os.environ.get("SMTP_USERNAME", "")
                            pwd = os.environ.get("SMTP_PASSWORD", "")
                            client.login(user, pwd)
                        client.send_message(msg)
                '''
            ).strip()
        )

    if needs_commands or any(e.get("kind") == "command" for e in spec.events):
        sections.append(
            textwrap.dedent(
                '''
                def run_allowlisted_command(
                    program: str,
                    arguments: str,
                    working_dir: Path,
                    allowed_commands: list[str] | tuple[str, ...],
                    timeout: int = 30,
                ) -> None:
                    prog_path = Path(program)
                    allowed_resolved = {Path(item).resolve() for item in allowed_commands}
                    allowed_names = {str(item).lower() for item in allowed_commands}
                    resolved_prog = prog_path.resolve() if prog_path.exists() else None
                    if (resolved_prog not in allowed_resolved) and (program.lower() not in allowed_names):
                        raise PermissionError(f"Command is not in allowed_commands: {program}")
                    working_dir.mkdir(parents=True, exist_ok=True)
                    argv = [str(resolved_prog or program), *shlex.split(arguments, posix=(os.name != "nt"))]
                    argv = [part.strip(\'"\') if os.name == "nt" and len(part) >= 2 and part[0] == part[-1] == \'"\' else part for part in argv]
                    subprocess.run(argv, cwd=str(working_dir), check=True, timeout=timeout)
                '''
            ).strip()
        )

    if any(e.get("kind") == "logging" for e in spec.events):
        sections.append(
            textwrap.dedent(
                '''
                def configure_workflow_logging(path: Path | None, columns_path: Path | None = None) -> None:
                    if columns_path is not None and path is None:
                        raise ValueError("--workflow-log-columns requires --workflow-log")
                    columns = json.loads(columns_path.read_text(encoding="utf-8-sig")) if columns_path else None

                    class _CsvFormatter(logging.Formatter):
                        def format(self, record: logging.LogRecord) -> str:
                            payload = json.loads(record.getMessage())
                            stream = io.StringIO(newline="")
                            csv.writer(stream).writerow(payload[k] for k in (columns or []))
                            return stream.getvalue().removesuffix("\\r\\n")

                    logger = logging.getLogger("workflow.audit")
                    logger.handlers.clear()
                    handler = logging.FileHandler(path, encoding="utf-8") if path else logging.StreamHandler()
                    handler.setFormatter(_CsvFormatter() if columns is not None else logging.Formatter("%(message)s"))
                    logger.addHandler(handler)
                    logger.setLevel(logging.INFO)
                    logger.propagate = False


                def _emit_workflow_log(
                    run_meta: tuple[str, str],
                    workflow_name: str,
                    event_id: str,
                    working_dir: Path,
                    warning_count: int,
                    error_count: int,
                    error: BaseException | None = None,
                ) -> None:
                    run_id, started_at = run_meta
                    payload = {
                        "run_id": run_id,
                        "workflow": workflow_name,
                        "event_id": event_id,
                        "started_at": started_at,
                        "finished_at": datetime.now(timezone.utc).isoformat(),
                        "status": "failed" if error is not None else "success",
                        "server": os.environ.get("ALTERYX_LOG_SERVER"),
                        "user": os.environ.get("USERNAME") or os.environ.get("USER"),
                        "computer_name": socket.gethostname(),
                        "working_dir": str(working_dir),
                        "warning_count": warning_count,
                        "error_count": error_count,
                        "conversion_error_count": None,
                        "error_type": type(error).__name__ if error is not None else None,
                        "error": str(error) if error is not None else None,
                    }
                    logger = logging.getLogger("workflow.audit")
                    logger.log(logging.ERROR if error is not None else logging.INFO, json.dumps(payload, ensure_ascii=False))
                '''
            ).strip()
        )

    if needs_events:
        has_log_ev = any(e.get("kind") == "logging" for e in spec.events)
        sections.append(
            textwrap.dedent(
                f'''
                def _run_event_hooks(config: dict, phase: str, warning_count: int, error: BaseException | None = None, run_meta=None) -> None:
                    hooks = config.get("events", {{}}).get("hooks", [])
                    if not hooks:
                        return
                    runtime = config.get("runtime", {{}})
                    input_dir = Path(runtime.get("input_dir") or PACKAGE_DIR)
                    output_dir = Path(runtime.get("output_dir") or (PACKAGE_DIR / "output"))
                    params = {{k: str(v) for k, v in config.get("parameters", {{}}).items()}}
                    warned = warning_count > 0
                    active_timings = {{"before"}} if phase == "before" else (
                        {{"after", "failure", "failure_or_warnings"}} if phase == "failure" else
                        {{"after", "success", "warnings" if warned else "clean_success", *({{"failure_or_warnings"}} if warned else set())}}
                    )

                    def fmt_str(template: str) -> str:
                        try:
                            return template.format(**params)
                        except KeyError:
                            return template

                    for hook in hooks:
                        if hook.get("when") not in active_timings:
                            continue
                        kind = hook.get("kind", "command")
                        if kind == "logging":
                            {"_emit_workflow_log(run_meta, hook.get('workflow_name', 'workflow'), str(hook['id']), input_dir, warning_count, int(error is not None), error)" if has_log_ev else "pass"}
                        elif kind in {{"email_draft", "email_smtp"}}:
                            atts = []
                            for spec_att in hook.get("attachments", []):
                                if str(spec_att).startswith("output:"):
                                    atts.append(output_dir / str(spec_att)[7:])
                                else:
                                    atts.append(input_dir / fmt_str(str(spec_att)))
                            dest = (output_dir / hook["draft_filename"]) if kind == "email_draft" and hook.get("draft_filename") else None
                            _deliver_email_message(
                                fmt_str(hook.get("sender", "")),
                                fmt_str(hook.get("recipient", "")),
                                fmt_str(hook.get("subject", "")),
                                fmt_str(hook.get("body", "")),
                                atts,
                                dest,
                                is_html=False,
                                host=fmt_str(hook.get("host", "")),
                                port=fmt_str(str(hook.get("port", "25"))),
                                security=fmt_str(hook.get("security", "plain")),
                                authentication=bool(hook.get("authentication", False)),
                                username=fmt_str(hook.get("username", "")),
                            )
                        else:
                            prog = fmt_str(str(hook.get("program", "")))
                            if not Path(prog).is_absolute() and (input_dir / prog).is_file():
                                prog = str((input_dir / prog).resolve())
                            work_dir_raw = fmt_str(str(hook.get("working_dir", "")))
                            ev_dir = Path(runtime["event_working_dir"]) if runtime.get("event_working_dir") else (
                                (input_dir / work_dir_raw) if work_dir_raw else input_dir
                            )
                            run_allowlisted_command(
                                prog,
                                fmt_str(str(hook.get("arguments", ""))),
                                ev_dir,
                                runtime.get("allowed_commands", ()),
                                int(hook.get("timeout", 30)),
                            )


                @contextmanager
                def workflow_lifecycle(config: dict):
                    run_meta = {"(str(uuid4()), datetime.now(timezone.utc).isoformat())" if has_log_ev else "None"}
                    with warnings.catch_warnings(record=True) as captured_warnings:
                        warnings.simplefilter("always", RuntimeWarning)
                        try:
                            _run_event_hooks(config, "before", 0, None, run_meta)
                            yield
                        except Exception as exc:
                            _run_event_hooks(config, "failure", len(captured_warnings), exc, run_meta)
                            raise
                        else:
                            _run_event_hooks(config, "success", len(captured_warnings), None, run_meta)
                '''
            ).strip()
        )

    return ("\n\n\n".join(sections) + "\n").replace(
        "_read_yxdb(path", f"{yxdb_reader}(path",
    ).replace("_read_excel(", f"{excel_reader}(").replace("_read_csv(", f"{csv_reader}(").replace(
        "_write_csv(path", f"{csv_writer}(path",
    ).replace("_write_excel(", f"{excel_writer}(")


def render_cli_py(spec: ConfigSpec, *, has_messages: bool = False) -> str:
    """Emit cli.py supporting both `python -m <pkg>` and `python <pkg>/cli.py`."""
    has_events = bool(spec.events)
    has_log = any(e.get("kind") == "logging" for e in spec.events)

    imports = [
        "from __future__ import annotations",
        "import argparse",
        "from datetime import date",
        "import math",
        "from pathlib import Path",
        "import sys",
    ]
    if has_messages:
        imports.append("import logging")

    bootstrap = textwrap.dedent(
        '''
        if __package__ in {None, ""}:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from {pkg_placeholder} import noop  # replaced dynamically if needed
        '''
    )
    # Use clean relative-or-local import fallback so both `python -m pkg` and `python pkg/cli.py` work!
    import_block = textwrap.dedent(
        f'''
        if __package__:
            from .io_utils import load_config{(", configure_workflow_logging" if has_log else "")}{(", workflow_lifecycle" if has_events else "")}
            from .runner import run_pipeline
        else:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from io_utils import load_config{(", configure_workflow_logging" if has_log else "")}{(", workflow_lifecycle" if has_events else "")}
            from runner import run_pipeline
        '''
    ).strip()

    meta_literal = repr(spec.parameter_meta)

    validation_block = textwrap.dedent(
        f'''
        PARAMETER_SCHEMA = {meta_literal}


        def _prompt_interactive(parameters: dict) -> dict:
            updated = dict(parameters)
            for key, meta in PARAMETER_SCHEMA.items():
                default = updated.get(key, "")
                label = meta.get("description") or meta.get("name") or key
                kind = meta.get("kind", "TextBox")
                if meta.get("choices"):
                    print(f"Choices for {{label}}: {{', '.join(map(str, meta['choices']))}}", file=sys.stderr)
                raw = input(f"{{label}} ({{kind}}) [{{default}}]: ").strip()
                if raw:
                    updated[key] = raw
            return updated


        def validate_parameters(parameters: dict) -> dict:
            cleaned = dict(parameters)
            for key, meta in PARAMETER_SCHEMA.items():
                val = cleaned.get(key)
                if meta.get("required") and (val is None or val == ""):
                    raise ValueError(f"Required parameter is empty: {{key}}")
                if key not in cleaned:
                    continue
                kind = meta.get("kind", "TextBox")
                if kind == "NumericUpDown":
                    val = float(val)
                    if not math.isfinite(val):
                        raise ValueError(f"Invalid numeric parameter: {{key}}")
                    val = int(val) if val.is_integer() else val
                    if meta.get("minimum") is not None and val < meta["minimum"]:
                        raise ValueError(f"Parameter {{key}} below minimum {{meta['minimum']}}")
                    if meta.get("maximum") is not None and val > meta["maximum"]:
                        raise ValueError(f"Parameter {{key}} above maximum {{meta['maximum']}}")
                elif kind in {{"BooleanGroup", "CheckBoxGroup", "RadioGroup", "RadioButtonGroup"}}:
                    if not isinstance(val, bool):
                        lowered = str(val).strip().lower()
                        if lowered not in {{"true", "false", "1", "0", "yes", "no", ""}}:
                            raise ValueError(f"Invalid boolean parameter: {{key}}")
                        val = lowered in {{"true", "1", "yes"}}
                else:
                    val = "" if val is None else str(val)
                    if kind == "Date" and val:
                        date.fromisoformat(val)
                if meta.get("choices") and val not in meta["choices"]:
                    raise ValueError(f"Invalid choice for {{key}}: {{val!r}} not in {{meta['choices']!r}}")
                if meta.get("expression_text") and isinstance(val, str):
                    if any(ch in val for ch in ("'", '"', "\\\\", "\\n", "\\r")):
                        raise ValueError(f"Parameter {{key}} contains unsupported quote or newline characters")
                cleaned[key] = val
            return cleaned
        '''
    ).strip()

    arg_lines = [
        "def main(argv: list[str] | None = None) -> int:",
        '    parser = argparse.ArgumentParser(description="Run the migrated native Python data pipeline")',
        '    parser.add_argument("--config", type=Path, help="Path to config.toml or config.json override")',
        '    parser.add_argument("--input-dir", type=Path)',
        '    parser.add_argument("--output-dir", type=Path)',
        '    parser.add_argument("--use-workflow-output-paths", action="store_true")',
        '    parser.add_argument("--interactive", action="store_true", help="Prompt interactively for parameters")',
        '    parser.add_argument("--event-working-dir", type=Path)',
        '    parser.add_argument("--command-working-dir", type=Path)',
        '    parser.add_argument("--allow-command", action="append", default=[])',
        '    parser.add_argument("--as-of", default=None)',
        '    parser.add_argument("--log-level", choices=["DEBUG", "INFO", "WARNING", "ERROR", "OFF"], default=None, help="Audit log verbosity level")',
        '    parser.add_argument("--log-format", choices=["text", "jsonl"], default=None, help="Audit log output format")',
        '    parser.add_argument("--audit-log", type=Path, default=None, help="Optional file path to write step-by-step audit records")',
        '    parser.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE")',
    ]
    if has_log:
        arg_lines.append('    parser.add_argument("--workflow-log", type=Path)')
        arg_lines.append('    parser.add_argument("--workflow-log-columns", type=Path)')
    reserved_flags = {"--as-of", "--config", "--input-dir", "--output-dir", "--log-level", "--log-format", "--audit-log"}
    for py_name in spec.parameters:
        flag = "--" + py_name.replace("_", "-")
        if flag in reserved_flags:
            continue
        arg_lines.append(f'    parser.add_argument({flag!r}, dest="param__{py_name}", default=argparse.SUPPRESS)')

    arg_lines.extend([
        "    args = parser.parse_args(argv)",
        "    param_overrides: dict = {}",
        "    for item in args.overrides:",
        '        k, sep, v = item.partition("=")',
        "        if not sep:",
        '            raise ValueError(f"Expected KEY=VALUE for --set, got {item!r}")',
        "        param_overrides[k.strip()] = v",
    ])
    for py_name in spec.parameters:
        flag = "--" + py_name.replace("_", "-")
        if flag in reserved_flags:
            continue
        arg_lines.append(f'    if hasattr(args, "param__{py_name}"):')
        arg_lines.append(f'        param_overrides[{py_name!r}] = getattr(args, "param__{py_name}")')
    if "__as_of__" in spec.python_param_names:
        as_of_py = spec.python_param_names["__as_of__"]
        arg_lines.append("    if args.as_of is not None:")
        arg_lines.append(f"        param_overrides[{as_of_py!r}] = args.as_of")

    arg_lines.extend([
        "    runtime_overrides: dict = {}",
        "    if args.allow_command:",
        '        runtime_overrides["allowed_commands"] = list(args.allow_command)',
        "    if args.event_working_dir is not None:",
        '        runtime_overrides["event_working_dir"] = str(args.event_working_dir.resolve())',
        "    if args.command_working_dir is not None:",
        '        runtime_overrides["command_working_dir"] = str(args.command_working_dir.resolve())',
        "    if args.as_of is not None:",
        '        runtime_overrides["as_of"] = args.as_of',
        "    logging_overrides: dict = {}",
        "    if args.log_level is not None:",
        '        logging_overrides["level"] = args.log_level',
        '        logging_overrides["enabled"] = args.log_level != "OFF"',
        "    if args.log_format is not None:",
        '        logging_overrides["format"] = args.log_format',
        "    if args.audit_log is not None:",
        '        logging_overrides["file"] = str(args.audit_log.resolve())',
        "    merged_overrides: dict = {}",
        "    if param_overrides:",
        '        merged_overrides["parameters"] = param_overrides',
        "    if runtime_overrides:",
        '        merged_overrides["runtime"] = runtime_overrides',
        "    if logging_overrides:",
        '        merged_overrides["logging"] = logging_overrides',
        "    config = load_config(",
        "        args.config,",
        "        overrides=merged_overrides or None,",
        "        input_dir=args.input_dir,",
        "        output_dir=args.output_dir,",
        "        use_workflow_output_paths=args.use_workflow_output_paths,",
        "    )",
        "    if args.interactive:",
        '        config["parameters"] = _prompt_interactive(config.get("parameters", {}))',
        '    config["parameters"] = validate_parameters(config.get("parameters", {}))',
    ])
    if has_messages:
        arg_lines.append("    logging.basicConfig(level=logging.INFO)")
    if has_log:
        arg_lines.append("    configure_workflow_logging(args.workflow_log, args.workflow_log_columns)")
    if has_events:
        arg_lines.append("    with workflow_lifecycle(config):")
        arg_lines.append("        result = run_pipeline(config)")
    else:
        arg_lines.append("    result = run_pipeline(config)")
    arg_lines.extend([
        '    print(result["output_dir"])',
        "    return 0",
        "",
        "",
        'if __name__ == "__main__":',
        "    raise SystemExit(main())",
    ])

    del bootstrap
    return "\n".join(imports) + "\n\n" + import_block + "\n\n\n" + validation_block + "\n\n\n" + "\n".join(arg_lines) + "\n"

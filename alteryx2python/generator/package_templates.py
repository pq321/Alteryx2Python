"""Clean, framework-free Python module templates for Phase 2 generated packages."""

from __future__ import annotations

import textwrap
from typing import Any

from alteryx2python.generator.config_extractor import ConfigSpec


def render_init_py() -> str:
    return '"""Generated native Python data pipeline package."""\n\nfrom .pipeline import run_pipeline\n\n__all__ = ["run_pipeline"]\n'


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

    sections: list[str] = ['"""Configuration loading and native table I/O utilities."""\n\n' + "\n".join(sorted(set(imports)))]

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
                base_dir = PACKAGE_DIR
                if config_path is not None:
                    cfg_file = Path(config_path).resolve()
                    config = _deep_merge(config, _parse_config_file(cfg_file))
                    base_dir = cfg_file.parent
                if overrides:
                    config = _deep_merge(config, overrides)
                runtime = config.setdefault("runtime", {})
                resolved_in = Path(input_dir or runtime.get("input_dir") or base_dir).resolve()
                resolved_out = Path(output_dir or runtime.get("output_dir") or (base_dir / "output")).resolve()
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

    # Delimited & Excel readers
    sections.append(
        textwrap.dedent(
            '''
            def _detect_legacy_encoding(sample: bytes, decode_error: UnicodeDecodeError, source: Path) -> str:
                from charset_normalizer import from_bytes

                if len(sample) == 65536 and b"\\n" in sample:
                    sample = sample.rsplit(b"\\n", 1)[0]
                if sample.isascii():
                    sample = decode_error.object[max(0, decode_error.start - 1024) : decode_error.start + 4096]
                matches = list(from_bytes(sample, cp_isolation=["cp932", "gb18030", "big5", "cp949", "cp1251", "cp1252"]))
                if matches:
                    best = matches[0]
                    ambiguous = any(
                        str(m) != str(best) and m.chaos - best.chaos < 0.02 and (best.coherence - m.coherence < 0.1)
                        for m in matches[1:]
                    )
                    if not ambiguous:
                        return str(best.encoding)
                raise ValueError(f"Cannot determine CSV encoding for {source}") from decode_error


            def read_input_table(config: dict, key: str) -> pd.DataFrame:
                entry = config["inputs"][key]
                path = resolve_input_path(config, entry)
                fmt = entry.get("format", "csv")
                has_header = bool(entry.get("has_header", True))
                header = 0 if has_header else None
                skiprows = int(entry.get("skip_rows", 0))
                nrows = entry.get("max_rows")

                if fmt == "excel":
                    kwargs: dict = {
                        "header": header,
                        "skiprows": skiprows,
                        "dtype": object,
                        "keep_default_na": False,
                        "na_values": [""],
                    }
                    if nrows is not None:
                        kwargs["nrows"] = int(nrows)
                    if "sheet_name" in entry:
                        kwargs["sheet_name"] = entry["sheet_name"]
                    if "usecols" in entry:
                        kwargs["usecols"] = entry["usecols"]
                    df = pd.read_excel(path, **kwargs).infer_objects()
                else:
                    delimiter = str(entry.get("delimiter", ","))
                    encoding = entry.get("encoding")
                    csv_opts: dict = {"sep": delimiter, "header": header, "skiprows": skiprows}
                    if nrows is not None:
                        csv_opts["nrows"] = int(nrows)
                    if encoding == "cp932":
                        df = pd.read_csv(path, encoding=encoding, dtype=str, keep_default_na=False, na_values=[""], **csv_opts)
                    elif encoding not in {None, "", "utf-8", "utf-8-sig", "utf8"}:
                        df = pd.read_csv(path, encoding=encoding, **csv_opts)
                    else:
                        with open(path, "rb") as handle:
                            prefix = handle.read(4)
                        if prefix.startswith((codecs.BOM_UTF32_LE, codecs.BOM_UTF32_BE)):
                            df = pd.read_csv(path, encoding="utf-32", **csv_opts)
                        elif prefix.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
                            df = pd.read_csv(path, encoding="utf-16", **csv_opts)
                        else:
                            try:
                                df = pd.read_csv(path, encoding="utf-8-sig", **csv_opts)
                            except UnicodeDecodeError as err:
                                with open(path, "rb") as handle:
                                    detected = _detect_legacy_encoding(handle.read(65536), err, path)
                                df = pd.read_csv(path, encoding=detected, dtype=str, keep_default_na=False, na_values=[""], **csv_opts)

                if not has_header:
                    df.columns = [f"F{idx}" for idx in range(1, len(df.columns) + 1)]
                return df
            '''
        ).strip()
    )

    if spec.references:
        sections.append(
            textwrap.dedent(
                '''
                def read_reference_table(config: dict, key: str) -> pd.DataFrame:
                    entry = config["references"][key]
                    rel_path = Path(entry["path"])
                    path = rel_path if rel_path.is_absolute() else (PACKAGE_DIR / rel_path)
                    df = pd.read_csv(path, dtype=object, keep_default_na=False)
                    cell_params = entry.get("cell_parameters") or {}
                    params = config.get("parameters", {})
                    for coord, param_name in cell_params.items():
                        r_str, c_str = coord.split(":", 1)
                        if param_name in params:
                            df.iat[int(r_str), int(c_str)] = str(params[param_name])
                    null_rows = entry.get("null_rows") or {}
                    for col, indices in null_rows.items():
                        if col in df.columns:
                            for r_idx in indices:
                                if f"{r_idx}:{list(df.columns).index(col)}" not in cell_params:
                                    df.at[r_idx, col] = None
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
            ).strip()
        )

    # Output writer
    writer_code = textwrap.dedent(
        '''
        def _format_compat_cell(value: object) -> str:
            if value is None or (not isinstance(value, str) and pd.isna(value)):
                return ""
            if isinstance(value, pd.Timestamp):
                if value.hour == 0 and value.minute == 0 and value.second == 0 and value.microsecond == 0:
                    return value.date().isoformat()
                return str(value)
            if isinstance(value, float) and value == int(value) and abs(value) < 1e15:
                return str(int(value))
            return str(value)


        def write_output_table(df: pd.DataFrame, config: dict, key: str) -> Path:
            entry = config["outputs"][key]
            fmt = entry.get("format", "csv")
            max_rows = entry.get("max_rows")
            out_df = df.head(int(max_rows)) if max_rows is not None else df

            if fmt == "excel":
                path = resolve_output_path(config, entry)
                path.parent.mkdir(parents=True, exist_ok=True)
                sheet_name = str(entry.get("sheet_name") or "Sheet1")
                has_header = bool(entry.get("has_header", True))
                with pd.ExcelWriter(path, engine="openpyxl") as writer:
                    out_df.to_excel(writer, sheet_name=sheet_name, index=False, header=has_header)
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
                    body_field = str(entry.get("body_field") or "Report")
                    fragments = [str(v) for v in out_df.get(body_field, pd.Series(dtype=object)) if v is not None and not pd.isna(v)]
                    html_body = "<html><body>" + "\\n".join(fragments) + "</body></html>"
                    attachments = [output_dir / name for name in entry.get("attachments", [])]
                    dest = resolve_output_path(config, entry) if fmt == "email_draft" else None
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
            rendered = out_df.astype(object)
            for idx in range(len(rendered.columns)):
                rendered.iloc[:, idx] = [_format_compat_cell(v) for v in rendered.iloc[:, idx]]
            if not has_header and len(rendered.columns) == 1:
                values = [str(v) for v in rendered.iloc[:, 0]]
                path.write_text(line_terminator.join(values) + line_terminator, encoding=encoding, newline="")
            else:
                rendered.to_csv(
                    path,
                    index=False,
                    header=has_header,
                    sep=delimiter,
                    lineterminator=line_terminator,
                    encoding=encoding,
                )
            return path
            '''
        ).strip(),
        "    ",
    )
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

    return "\n\n\n".join(sections) + "\n"


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
            from .pipeline import run_pipeline
        else:
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from io_utils import load_config{(", configure_workflow_logging" if has_log else "")}{(", workflow_lifecycle" if has_events else "")}
            from pipeline import run_pipeline
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
                if key not in cleaned:
                    continue
                val = cleaned[key]
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
                if meta.get("required") and (val is None or val == ""):
                    raise ValueError(f"Required parameter is empty: {{key}}")
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
        '    parser.add_argument("--set", dest="overrides", action="append", default=[], metavar="KEY=VALUE")',
    ]
    if has_log:
        arg_lines.append('    parser.add_argument("--workflow-log", type=Path)')
        arg_lines.append('    parser.add_argument("--workflow-log-columns", type=Path)')
    for py_name in spec.parameters:
        flag = "--" + py_name.replace("_", "-")
        if flag in {"--as-of", "--config", "--input-dir", "--output-dir"}:
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
        if flag in {"--as-of", "--config", "--input-dir", "--output-dir"}:
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
        "    merged_overrides: dict = {}",
        "    if param_overrides:",
        '        merged_overrides["parameters"] = param_overrides',
        "    if runtime_overrides:",
        '        merged_overrides["runtime"] = runtime_overrides',
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

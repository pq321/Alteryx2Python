"""Explicit HTML report, draft email and opt-in SMTP delivery profiles."""
from __future__ import annotations

import hashlib
import html
import json
import mimetypes
import os
import shlex
import shutil
import subprocess
import smtplib
import ssl
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path, PureWindowsPath

import pandas as pd
from alteryx2python.tools.dbfileoutput import delivery_output_path, ensure_output_directory


PROFILE = 'html-draft-v1'
SMTP_PROFILE = 'html-smtp-v1'
XLSX_PROFILE = 'xlsx-table-v1'


def xlsx_report_table(frame, fields, group_fields, show_header):
    if 'Table' in group_fields:
        raise ValueError("Table cannot also be a group field")
    groups = frame.groupby(group_fields, sort=False, dropna=False) if group_fields else [((), frame)]
    records = []
    for keys, group in groups:
        if group_fields and not isinstance(keys, tuple):
            keys = (keys,)
        selected = group.loc[:, fields] if fields else group
        records.append({
            **dict(zip(group_fields, keys)),
            "Table": selected.to_json(orient="split", index=False, date_format="iso", double_precision=15),
        })
    result = pd.DataFrame(records, columns=[*group_fields, "Table"])
    result.attrs["xlsx_header"] = show_header
    return result


def xlsx_render_options(config):
    filename = PureWindowsPath(config.get("output_file") or "report.xlsx").name
    field = config.get("data_field") or "Table"
    if (Path(filename).suffix.lower() != ".xlsx" or config.get("temp_file_type", "").lower() not in {"", "xlsx"}
            or field not in {"Table", "Layout"} or config.get("show_header") or config.get("show_footer")):
        raise NotImplementedError("XLSX Render supports basic table workbooks without a page header or footer")
    group = config.get("group_field") if config.get("batch_mode") else None
    modifier = config.get("filename_modifier") if group else None
    if config.get("batch_mode") and (not group or modifier not in {"Prepend", "ReplacePath"}):
        raise NotImplementedError("Batched XLSX Render requires a group field and Prepend or ReplacePath filename mode")
    return filename, field, group, modifier


def xlsx_layout_options(config):
    mode = config.get("grouping_mode") or "PerRecord"
    groups = config.get("grouping_fields", [])
    fields = config.get("layout_fields") or ["Table"]
    orientation = str(config.get("orientation", "")).lower()
    separator = str(config.get("separator", "")).lower()
    section_field = config.get("section_name_for_group") or None
    named_sections = separator == "breaking" or orientation == "breaking"
    if (mode not in {"PerRecord", "PerGroup"} or (mode == "PerGroup" and not groups)
            or orientation not in {"", "v", "vertical", "breaking"}
            or separator not in {"", "continuous", "breaking"}
            or any(field not in {"Table", "Layout"} for field in fields)
            or config.get("section_name_for_all_records")):
        raise NotImplementedError("XLSX Layout supports vertical Table fragments per record or group")
    if named_sections and (mode != "PerGroup" or not section_field or section_field not in groups):
        raise NotImplementedError("XLSX section breaks require a named section field among the grouping fields")
    if section_field and not named_sections:
        raise NotImplementedError("XLSX section names require the Breaking layout option")
    return groups if mode == "PerGroup" else [], fields, section_field


def _xlsx_fragments(cell):
    fragment = json.loads(cell)
    return fragment["tables"] if "tables" in fragment else [fragment]


def xlsx_report_layout(frame, groups, fields, section_field=None):
    if "Layout" in groups:
        raise ValueError("Layout cannot also be a group field")
    if not groups:
        result = frame.drop(columns=[field for field in fields if field in frame]).copy()
        result["Layout"] = [
            json.dumps({"tables": [table for field in fields for table in _xlsx_fragments(row[field])]})
            for row in frame.to_dict("records")
        ]
    else:
        records = []
        for keys, entries in frame.groupby(groups, sort=False, dropna=False):
            keys = keys if isinstance(keys, tuple) else (keys,)
            tables = [table for row in entries.to_dict("records")
                      for field in fields for table in _xlsx_fragments(row[field])]
            record = dict(zip(groups, keys))
            fragment = {"tables": tables}
            if section_field is not None:
                label = record[section_field]
                if pd.isna(label):
                    raise ValueError(f"XLSX Layout section field {section_field!r} contains a null value")
                fragment["section_name"] = str(label)
            records.append({**record, "Layout": json.dumps(fragment)})
        result = pd.DataFrame(records, columns=[*groups, "Layout"])
    result.attrs = frame.attrs.copy()
    return result


def _xlsx_sheet_data(tables):
    columns = tables[0]["columns"]
    if any(table["columns"] != columns for table in tables):
        raise ValueError("XLSX Render received tables with different columns in one worksheet")
    return pd.DataFrame([row for table in tables for row in table["data"]], columns=columns)


def _xlsx_workbook_sheets(cells):
    fragments = [json.loads(cell) for cell in cells]
    if not any("section_name" in fragment for fragment in fragments):
        tables = [table for fragment in fragments for table in fragment.get("tables", [fragment])]
        return {"sheet1": _xlsx_sheet_data(tables)} if tables else {}

    sheets, used = {}, set()
    for fragment in fragments:
        name = fragment.get("section_name")
        if (not isinstance(name, str) or not name.strip() or len(name) > 31
                or any(char in name for char in ":\\/?*[]\r\n") or name.startswith("'") or name.endswith("'")):
            raise ValueError(f"Invalid XLSX section worksheet name: {name!r}")
        if name.casefold() in used:
            raise ValueError(f"Duplicate XLSX section worksheet name: {name!r}")
        used.add(name.casefold())
        sheets[name] = _xlsx_sheet_data(fragment["tables"])
    return sheets


def render_xlsx_tables(frame, destination, data_field, group=None, modifier=None, *, workflow_base=None):
    groups = frame.groupby(group, sort=False, dropna=False) if group else [(None, frame)]
    outputs = {}
    for label, rows in groups:
        name = destination.name
        path = destination
        if modifier == "ReplacePath":
            if not isinstance(label, str) or not label.strip() or label.endswith(("/", "\\")):
                raise ValueError(f"Invalid XLSX Render replacement path: {label!r}")
            name = PureWindowsPath(label).name
            if Path(name).suffix.lower() != ".xlsx" or any(char in name for char in ':*?"<>|\r\n'):
                raise ValueError(f"XLSX Render replacement requires an .xlsx filename: {label!r}")
            path = delivery_output_path(label, destination.parent, workflow_base, workflow_base is not None)
        elif group:
            prefix = str(label).strip()
            if pd.isna(label) or not prefix or any(char in prefix for char in '/\\:*?"<>|\r\n') or prefix in {".", ".."}:
                raise ValueError(f"Invalid XLSX Render filename group: {label!r}")
            name = prefix + name
            path = destination.with_name(name)
        identity = str(path).casefold()
        if identity in outputs:
            raise ValueError(f"Duplicate XLSX Render target: {path}")
        sheets = _xlsx_workbook_sheets(rows[data_field])
        if sheets:
            outputs[identity] = (path, sheets)
    header = frame.attrs.get("xlsx_header", True)
    for path, sheets in outputs.values():
        ensure_output_directory(path.parent)
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            for name, table in sheets.items():
                table.to_excel(writer, sheet_name=name, index=False, header=header)


def report_table(frame, fields, show_header=True):
    selected = frame.loc[:, fields] if fields else frame
    return pd.DataFrame({'Report': [selected.to_html(index=False, border=0, header=show_header, escape=True)]})


def report_text(message, output_field='Report'):
    return pd.DataFrame({output_field: [f'<p>{html.escape(message)}</p>']})


def report_layout(frame, fields):
    fields = fields or ['Report']
    fragments = [str(row[field]) for row in frame.to_dict('records') for field in fields]
    return pd.DataFrame({'Report': ['\n'.join(fragments)]})


def render_html(frame, data_field, destination):
    body = '\n'.join(str(value) for value in frame[data_field])
    document = '<!doctype html>\n<html><head><meta charset="utf-8"></head><body>\n' + body + '\n</body></html>\n'
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding='utf-8', newline='')


def email_message(frame, sender, recipient, subject, body_field, attachments, draft=True):
    if len(frame.index) != 1:
        raise ValueError('Email profile requires exactly one message record')
    message = EmailMessage(policy=SMTP)
    message['From'] = sender
    message['To'] = recipient
    message['Subject'] = subject
    if draft:
        message['X-Unsent'] = '1'
    message.set_content('This message contains an HTML report.')
    message.add_alternative(str(frame.iloc[0][body_field]), subtype='html')
    for attachment in attachments:
        path = Path(attachment)
        media = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        main, sub = media.split('/', 1)
        message.add_attachment(path.read_bytes(), maintype=main, subtype=sub, filename=path.name)
    # Stable MIME boundaries make artifacts reproducible across both phases.
    for index, part in enumerate(message.walk()):
        if part.is_multipart():
            part.set_boundary('migration-' + hashlib.sha256((subject + str(index)).encode()).hexdigest()[:24])
    return message


def draft_email(frame, sender, recipient, subject, body_field, attachments, destination):
    message = email_message(frame, sender, recipient, subject, body_field, attachments)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(message.as_bytes())


def send_email(frame, sender, recipient, subject, body_field, attachments):
    message = email_message(frame, sender, recipient, subject, body_field, attachments, draft=False)
    smtp_send(message)


def smtp_send(message, host='', port='', security='', authentication=None, username=''):
    server = os.environ.get('SMTP_HOST') or host
    security = (os.environ.get('SMTP_SECURITY') or security or 'starttls').lower()
    if not server or security not in {'starttls', 'ssl', 'plain'}:
        raise ValueError('SMTP_HOST and a supported SMTP_SECURITY are required')
    port = int(os.environ.get('SMTP_PORT') or port or ('465' if security == 'ssl' else '587'))
    if not 1 <= port <= 65535:
        raise ValueError('SMTP_PORT must be between 1 and 65535')
    username = (os.environ.get('SMTP_USERNAME') or username) if authentication is not False else None
    password = os.environ.get('SMTP_PASSWORD') if authentication is not False else None
    if bool(username) != bool(password):
        raise ValueError('SMTP_USERNAME and SMTP_PASSWORD must be supplied together')
    if authentication is True and not username:
        raise ValueError('Authenticated email event requires SMTP_USERNAME and SMTP_PASSWORD')
    tls = ssl.create_default_context()
    connection = smtplib.SMTP_SSL(server, port, timeout=30, context=tls) if security == 'ssl' else smtplib.SMTP(server, port, timeout=30)
    with connection as client:
        if security == 'starttls':
            client.starttls(context=tls)
        if username:
            client.login(username, password)
        refused = client.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)


def deliver_event_email(sender, recipient, subject, body, attachments, destination=None,
                       host='', port='', security='', authentication=False, username=''):
    message = EmailMessage(policy=SMTP)
    message['From'], message['To'], message['Subject'] = sender, recipient, subject
    message.set_content(body)
    for attachment in attachments:
        path = Path(attachment)
        media = mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
        main, sub = media.split('/', 1)
        message.add_attachment(path.read_bytes(), maintype=main, subtype=sub, filename=path.name)
    for index, part in enumerate(message.walk()):
        if part.is_multipart():
            part.set_boundary('migration-' + hashlib.sha256((subject + str(index)).encode()).hexdigest()[:24])
    if destination is None:
        smtp_send(message, host, port, security, authentication, username)
    else:
        message['X-Unsent'] = '1'
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(message.as_bytes())


def command_arguments(arguments):
    if not isinstance(arguments, str):
        return list(arguments)
    if os.name != 'nt':
        return shlex.split(arguments)
    import ctypes
    from ctypes import wintypes
    parse = ctypes.windll.shell32.CommandLineToArgvW
    parse.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    parse.restype = ctypes.POINTER(wintypes.LPWSTR)
    release = ctypes.windll.kernel32.LocalFree
    release.argtypes = [ctypes.c_void_p]
    release.restype = ctypes.c_void_p
    count = ctypes.c_int()
    pointer = parse('command ' + arguments, ctypes.byref(count))
    if not pointer:
        raise OSError('Cannot parse Windows command arguments')
    try:
        return [pointer[index] for index in range(1, count.value)]
    finally:
        release(pointer)


def run_checked_command(program, arguments, working_dir, input_frame, input_file, output_file, allowed_programs, timeout=30):
    candidate = Path(working_dir) / program
    if not Path(program).is_absolute() and candidate.is_file():
        program = str(candidate.resolve())
    executable = shutil.which(program) or program
    resolved = Path(executable).resolve()
    allowed = {Path(shutil.which(value) or value).resolve() for value in allowed_programs}
    if resolved not in allowed:
        raise PermissionError(f'Command is not explicitly allowed: {program}')
    directory = Path(working_dir)
    directory.mkdir(parents=True, exist_ok=True)
    if input_file:
        input_frame.to_csv(directory / input_file, index=False)
    argv = command_arguments(arguments)
    command = [str(resolved), *argv]
    if os.name == 'nt' and resolved.suffix.lower() in {'.bat', '.cmd'}:
        if any(any(char in value for char in '&|<>^%\r\n') for value in [str(resolved), *argv]):
            raise ValueError('Batch command arguments contain unsupported shell metacharacters')
        command = subprocess.list2cmdline([os.environ.get('COMSPEC', 'cmd.exe'), '/d', '/s', '/c']) + ' "' + subprocess.list2cmdline([str(resolved), *argv]) + '"'
    subprocess.run(command, cwd=directory, check=True, timeout=timeout,
                   capture_output=True, text=True,
                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    if output_file:
        return pd.read_csv(directory / output_file)
    return input_frame.copy() if input_frame is not None else pd.DataFrame()


def email_tool(inputs, config, context):
    runtime = context.runtime_config or {}
    profile = runtime.get('delivery_profile')
    if profile not in {PROFILE, SMTP_PROFILE}:
        raise NotImplementedError('Email requires an explicit html-draft-v1 or html-smtp-v1 delivery profile')
    if config.get('unsupported_options'):
        raise NotImplementedError(f"Email configuration needs a template: {config['unsupported_options']}")
    frame = inputs.get('Input')
    if frame is None:
        raise KeyError('Email requires Input')
    attachments = [Path(runtime['output_dir']) / Path(value).name for value in config.get('attachments', [])]
    arguments = (frame, config.get('from', ''), config.get('to', ''), config.get('subject', ''), config.get('body') or 'Report', attachments)
    destination = None
    if profile == SMTP_PROFILE:
        send_email(*arguments)
    else:
        destination = Path(runtime['output_dir']) / f"email-{config['node_id']}.eml"
        draft_email(*arguments, destination)
    context.record_node(node_id=str(config['node_id']), tool_type='Email',
                        source_tool_id=config.get('source_tool_id'), inputs=inputs, outputs={}, status='success',
                        config={'delivery_profile': profile, 'draft_file': str(destination) if destination else None, 'sent': profile == SMTP_PROFILE})
    return {}

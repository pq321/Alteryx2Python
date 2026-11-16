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
from alteryx2python.tools.dbfileoutput import write_xlsx


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
            or field != "Table" or config.get("show_header") or config.get("show_footer")):
        raise NotImplementedError("XLSX Render supports basic table workbooks without a page header or footer")
    group = config.get("group_field") if config.get("batch_mode") else None
    if config.get("batch_mode") and (not group or config.get("filename_modifier") != "Prepend"):
        raise NotImplementedError("Batched XLSX Render requires a group field and Prepend filename mode")
    return filename, field, group


def render_xlsx_tables(frame, destination, data_field, group=None):
    groups = frame.groupby(group, sort=False, dropna=False) if group else [(None, frame)]
    outputs = {}
    for label, rows in groups:
        name = destination.name
        if group:
            prefix = str(label).strip()
            if pd.isna(label) or not prefix or any(char in prefix for char in '/\\:*?"<>|\r\n') or prefix in {".", ".."}:
                raise ValueError(f"Invalid XLSX Render filename group: {label!r}")
            name = prefix + name
        if name.casefold() in outputs:
            raise ValueError(f"Duplicate XLSX Render target: {name}")
        tables = [json.loads(cell) for cell in rows[data_field]]
        if not tables:
            continue
        columns = tables[0]["columns"]
        if any(table["columns"] != columns for table in tables):
            raise ValueError("XLSX Render received tables with different columns")
        outputs[name.casefold()] = (destination.with_name(name), pd.DataFrame(
            [row for table in tables for row in table["data"]], columns=columns
        ))
    for path, table in outputs.values():
        write_xlsx(path, table, "sheet1", header=frame.attrs.get("xlsx_header", True))


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

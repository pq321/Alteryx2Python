"""Explicit portable HTML/draft profile; no network email is sent."""
from __future__ import annotations

import hashlib
import html
import mimetypes
import os
import shlex
import shutil
import subprocess
from email.message import EmailMessage
from email.policy import SMTP
from pathlib import Path

import pandas as pd


PROFILE = 'html-draft-v1'


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


def draft_email(frame, sender, recipient, subject, body_field, attachments, destination):
    if len(frame.index) != 1:
        raise ValueError('Draft profile requires exactly one message record')
    message = EmailMessage(policy=SMTP)
    message['From'] = sender
    message['To'] = recipient
    message['Subject'] = subject
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
    if runtime.get('delivery_profile') != PROFILE:
        raise NotImplementedError('Email requires the explicit html-draft-v1 delivery profile')
    if config.get('unsupported_options'):
        raise NotImplementedError(f"Email configuration needs a template: {config['unsupported_options']}")
    frame = inputs.get('Input')
    if frame is None:
        raise KeyError('Email requires Input')
    destination = Path(runtime['output_dir']) / f"email-{config['node_id']}.eml"
    draft_email(frame, config.get('from', ''), config.get('to', ''), config.get('subject', ''),
                config.get('body', 'Report'),
                [Path(runtime['output_dir']) / Path(value).name for value in config.get('attachments', [])],
                destination)
    context.record_node(node_id=str(config['node_id']), tool_type='Email',
                        source_tool_id=config.get('source_tool_id'), inputs=inputs, outputs={}, status='success',
                        config={'delivery_profile': PROFILE, 'draft_file': str(destination), 'sent': False})
    return {}

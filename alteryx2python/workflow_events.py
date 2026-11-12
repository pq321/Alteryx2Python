"""Parse preserved workflow events; unknown enabled events fail explicitly."""
from __future__ import annotations

from xml.etree import ElementTree as ET


def attachment_bindings(workflow, *, redirect_sinks=False):
    """Map configured sink paths to their relocated output filenames."""
    import os
    from pathlib import Path
    bindings = {}
    for node in workflow.nodes:
        config = node.config.get('normalized', node.config)
        if node.tool_type == 'DbFileOutput' and redirect_sinks:
            filename = str(config.get('file', '')).partition('|||')[0]
        elif node.tool_type == 'PortfolioComposerRender':
            filename = str(config.get('output_file') or 'report.html')
        else:
            continue
        if filename:
            for path in [Path(filename), Path(config.get('base_dir', '.')) / filename]:
                bindings[os.path.normcase(os.path.normpath(str(path)))] = Path(filename).name
    return bindings


def attachment_output(filename, bindings):
    import os
    return bindings.get(os.path.normcase(os.path.normpath(filename)))


def workflow_events(source_xml):
    if not source_xml:
        return []
    root = ET.fromstring(source_xml)
    events = root.find('./Properties/Events')
    if events is None:
        return []
    enabled = events.find('Enabled')
    if enabled is not None and enabled.get('value', enabled.text or 'True').lower() not in {'true', '1'}:
        return []
    result = []
    times = {'beforerun': 'before', 'before': 'before', 'afterrun': 'after', 'after': 'after',
             'afterrunwithout errors': 'success', 'afterrunwithouterrors': 'success',
             'afterrunwitherrors': 'failure', 'afterrunwitherrorsorwarnings': 'failure_or_warnings',
             'afterrunwithwarnings': 'warnings', 'success': 'success', 'failure': 'failure',
             'afterrunwithouterrorsorwarnings': 'clean_success', 'afternoerrors': 'success',
             'afternoerrorsnowarnings': 'clean_success',
             'aftererrors': 'failure', 'afterwarnings': 'warnings', 'aftererrorswarnings': 'failure_or_warnings'}
    times.update(aftererror='failure', afternoerror='success')
    for index, event in enumerate(events.findall('Event')):
        def value(*names, default=''):
            for name in names:
                child = event.find(name)
                if child is not None:
                    return child.get('value', child.text or default)
                if name in event.attrib:
                    return event.get(name)
            return default
        if value('Enabled', default='True').lower() not in {'true', '1'}:
            continue
        kind = value('EventType', 'Type', 'name', default='RunCommand')
        kind = kind.lower().replace(' ', '')
        mail = value('SendMail', default='False').lower() in {'true', '1'} or kind in {'sendemail', 'sendmail', 'email'}
        if kind not in {'runcommand', 'command', 'sendemail', 'sendmail', 'email'}:
            raise NotImplementedError(f'Enabled workflow event {index} has unsupported type: {kind}')
        raw_when = value('When', 'EventWhen', 'RunWhen')
        if raw_when.lower() == 'disabled':
            continue
        when = times.get(raw_when.lower().replace(' ', ''))
        if when is None:
            raise NotImplementedError(f'Unknown enabled workflow event timing: {raw_when}')
        if mail:
            encryption = value('email_Encryption', default='None').lower()
            security = {'none': 'plain', 'ssl': 'ssl', 'tls': 'starttls', 'starttls': 'starttls'}.get(encryption)
            if security is None:
                raise NotImplementedError(f'Unsupported email event encryption: {encryption}')
            result.append({'id': str(index), 'when': when, 'kind': 'email',
                           'sender': value('email_From'), 'recipient': value('email_To'),
                           'subject': value('email_Subject'), 'body': value('email_Body'),
                           'attachments': [item.get('value', item.text or '') for item in event.findall('email_Attachments/attachment')],
                           'host': value('email_SMTPServer', 'email_SMTP'),
                           'port': value('email_Port', default='25'), 'security': security,
                           'authentication': value('email_Authentication', default='False').lower() in {'true', '1'},
                           'username': value('email_Username'), 'dcm': event.find('Connection') is not None})
            continue
        program = value('cmd_Program', 'Command', 'ProgramName')
        if not program:
            raise ValueError(f'Workflow event {index} has no command')
        result.append({'id': str(index), 'when': when, 'program': program,
                       'arguments': value('cmd_CommandArguments', 'cmd_CommandLine', 'Arguments', 'CommandArguments'),
                       'working_dir': value('cmd_WorkingDir', 'WorkingDir', 'WorkingDirectory'),
                       'timeout': int(value('cmd_Timeout', 'Timeout', default='30') or '30') or 30})
    return result


def run_events(events, phase, context, attachment_paths=None):
    from pathlib import Path
    from alteryx2python.tools.delivery import run_checked_command
    runtime = context.runtime_config or {}
    if runtime.get('skip_workflow_events'):
        return
    warned = bool(context.warnings)
    selected = {'before'} if phase == 'before' else (
        {'after', 'failure', 'failure_or_warnings'} if phase == 'failure' else
        {'after', 'success', 'warnings' if warned else 'clean_success',
         'failure_or_warnings' if warned else 'success'})
    for event in events:
        if event['when'] not in selected:
            continue
        base = Path(runtime.get('input_dir') or runtime.get('workflow_dir') or Path.cwd())
        if event.get('kind') == 'email':
            from alteryx2python.tools.delivery import deliver_event_email, PROFILE, SMTP_PROFILE
            profile = runtime.get('delivery_profile')
            if profile not in {PROFILE, SMTP_PROFILE}:
                raise NotImplementedError('Email events require an explicit html-draft-v1 or html-smtp-v1 profile')
            if event['dcm'] and profile == SMTP_PROFILE:
                raise NotImplementedError('Email event DCM connection needs an explicit SMTP adapter')
            output_dir = Path(runtime.get('output_dir') or base / 'output')
            destination = output_dir / f"event-{event['id']}.eml" if profile == PROFILE else None
            attachments = []
            for item in event['attachments']:
                produced = attachment_output(item, attachment_paths or {})
                attachments.append(output_dir / produced if produced else base / item)
            deliver_event_email(event['sender'], event['recipient'], event['subject'], event['body'],
                attachments, destination,
                event['host'], event['port'], event['security'], event['authentication'], event['username'])
            context.record_diagnostic({'kind': 'workflow_event', 'event_id': event['id'],
                'when': event['when'], 'status': 'success', 'sent': profile == SMTP_PROFILE,
                'draft_file': str(destination) if destination else None})
            continue
        directory = Path(event['working_dir']) if event['working_dir'] else base
        if not directory.is_absolute():
            directory = base / directory
        directory = runtime.get('event_working_dir') or directory
        program = event['program']
        if not Path(program).is_absolute() and (base / program).is_file():
            program = str((base / program).resolve())
        run_checked_command(program, event['arguments'], directory, None, '', '',
                            runtime.get('allowed_commands', ()), event['timeout'])
        context.record_diagnostic({'kind': 'workflow_event', 'event_id': event['id'],
                                   'when': event['when'], 'status': 'success'})

"""Parse preserved workflow events; unknown enabled events fail explicitly."""
from __future__ import annotations

from xml.etree import ElementTree as ET


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
        if value('SendMail', default='False').lower() in {'true', '1'}:
            raise NotImplementedError('Mail workflow events require a dedicated draft configuration')
        if kind.lower().replace(' ', '') not in {'runcommand', 'command'}:
            raise NotImplementedError(f'Enabled workflow event {index} has unsupported type: {kind}')
        raw_when = value('When', 'EventWhen', 'RunWhen')
        when = times.get(raw_when.lower().replace(' ', ''))
        if when is None:
            raise NotImplementedError(f'Unknown enabled workflow event timing: {raw_when}')
        program = value('cmd_Program', 'Command', 'ProgramName')
        if not program:
            raise ValueError(f'Workflow event {index} has no command')
        result.append({'id': str(index), 'when': when, 'program': program,
                       'arguments': value('cmd_CommandLine', 'Arguments', 'CommandArguments'),
                       'working_dir': value('cmd_WorkingDir', 'WorkingDir', 'WorkingDirectory'),
                       'timeout': int(value('cmd_Timeout', 'Timeout', default='30') or '30') or 30})
    return result


def run_events(events, phase, context):
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

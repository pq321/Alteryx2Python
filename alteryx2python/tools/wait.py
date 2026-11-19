"""An explicit wait-seconds contract for workflow delay nodes."""
from __future__ import annotations

import math
import time
from pathlib import PureWindowsPath

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def is_crew_wait_macro(path):
    return PureWindowsPath(path).name.casefold() == 'crew_waitasecond.yxmc'


def wait_for_frame(frame, seconds, per_record=False):
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('Wait duration must be finite and nonnegative')
    if seconds:
        for _ in range(len(frame) if per_record else 1):
            time.sleep(seconds)
    return frame.copy()


def wait_seconds_tool(inputs, config, context):
    input_anchor = config.get('input_anchor', 'Input')
    if input_anchor not in inputs:
        raise KeyError(f'Wait tool requires {input_anchor}')
    seconds = float(config.get('seconds', 1))
    output_anchor = config.get('output_anchor', 'Output')
    audit = (context.runtime_config or {}).get('_workflow_audit', False)
    outputs = {output_anchor: wait_for_frame(inputs[input_anchor], 0 if audit else seconds, config.get('per_record', False))}
    context.record_node(node_id=str(config.get('node_id', 'unknown')), tool_type=config.get('tool_type', 'WaitASecond'),
                        source_tool_id=config.get('source_tool_id'), inputs=inputs, outputs=outputs,
                        status='success', config={'seconds': seconds, 'delay_replayed': not audit})
    return outputs


def parse_wait(raw):
    value = child(raw, 'Seconds')
    return ToolParserResult({'seconds': float(attributes(value).get('value', text(value, '1')))})


def parse_crew_wait(raw):
    values = raw.get('Value', [])
    if isinstance(values, dict):
        values = [values]
    duration = next((value for value in values if attributes(value).get('name') == 'Numeric Up Down (12)'), None)
    seconds = float(text(duration, '5'))
    if not seconds.is_integer() or not 0 <= seconds <= 36000:
        raise ValueError('CReW Wait A Second requires a whole number from 0 to 36000 seconds')
    return ToolParserResult({
        'seconds': int(seconds), 'per_record': True, 'tool_type': 'CReWWaitASecond',
        'input_anchor': 'Input7', 'output_anchor': 'Output8',
    })


IMPLEMENTATIONS = dict.fromkeys(('WaitASecond', 'WaitSeconds', 'CReWWaitASecond'), wait_seconds_tool)
ANCHORS = {'WaitASecond': (('Input',), ('Output',)), 'WaitSeconds': (('Input',), ('Output',)),
           'CReWWaitASecond': (('Input7',), ('Output8',))}
PARSERS = {'WaitASecond': parse_wait, 'WaitSeconds': parse_wait, 'CReWWaitASecond': parse_crew_wait}

"""An explicit wait-seconds contract for workflow delay nodes."""
from __future__ import annotations

import math
import time

from alteryx2python.parser.tool_parsers.common import ToolParserResult, attributes, child, text


def wait_seconds_tool(inputs, config, context):
    if 'Input' not in inputs:
        raise KeyError('WaitASecond requires Input')
    seconds = float(config.get('seconds', 1))
    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError('Wait duration must be finite and nonnegative')
    time.sleep(seconds)
    outputs = {'Output': inputs['Input'].copy()}
    context.record_node(node_id=str(config.get('node_id', 'unknown')), tool_type='WaitASecond',
                        source_tool_id=config.get('source_tool_id'), inputs=inputs, outputs=outputs,
                        status='success', config={'seconds': seconds})
    return outputs


def parse_wait(raw):
    value = child(raw, 'Seconds')
    return ToolParserResult({'seconds': float(attributes(value).get('value', text(value, '1')))})


IMPLEMENTATIONS = {'WaitASecond': wait_seconds_tool, 'WaitSeconds': wait_seconds_tool}
ANCHORS = {kind: (('Input',), ('Output',)) for kind in IMPLEMENTATIONS}
PARSERS = {kind: parse_wait for kind in IMPLEMENTATIONS}

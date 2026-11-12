"""Execute saved Python Tool programs using native boundary lowering."""
from __future__ import annotations

from textwrap import indent
from typing import Any

import pandas as pd

from alteryx2python.generator.python_tool import lower_python_script, saved_python_script
from alteryx2python.generator.source_linker import SourceLinker
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _extract_notebook_code(notebook):
    return saved_python_script({'notebook': notebook})


def jupytercode_tool(inputs: dict[str, pd.DataFrame], config: dict[str, Any], context: WorkflowContext) -> dict[str, pd.DataFrame]:
    script = saved_python_script(config)
    arguments = {anchor: f'_input_{index}' for index, anchor in enumerate(inputs)}
    constants = (context.runtime_config or {}).get('workflow_constants', {})
    linker = SourceLinker()
    body, anchors = lower_python_script(script, arguments, constants, linker)
    source = linker.render() + '\n\ndef python_tool(' + ', '.join(arguments.values()) + '):\n' + indent('\n'.join(body), '    ')
    namespace = {}
    exec(compile(source, '<Python Tool>', 'exec'), namespace)
    result = namespace['python_tool'](*inputs.values())
    outputs = dict(zip(anchors, (result,) if len(anchors) == 1 else result or ()))
    context.record_node(
        node_id=str(config.get('node_id', 'unknown')), tool_type='JupyterCode',
        source_tool_id=config.get('source_tool_id'), inputs=inputs, outputs=outputs, status='success',
        config={'external_code_executed': True, 'venv_name': config.get('venv_name', ''),
                'script_length': len(script), 'output_anchors': list(anchors)},
    )
    return outputs


class JupyterCodeTool(BaseTool):
    tool_type = 'JupyterCode'
    input_anchors = ('Input',)
    output_anchors = ()

    def execute(self, inputs, config, context):
        return jupytercode_tool(inputs, config, context)


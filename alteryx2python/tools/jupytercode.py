from __future__ import annotations

import io
import json
import re
import contextlib
from types import SimpleNamespace
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


class _AlteryxBridge:
    """Implements the subset of the ayx Python Tool API the engine exposes.

    - Alteryx.read("#1") returns the incoming DataFrame of anchor #1.
    - Alteryx.write(df, "#1") publishes df as the outgoing anchor #1.
    - Alteryx.getIncomingAnchorNames / getOutgoingAnchorNamesMap are helpers
      the official SDK documents for multi-anchor tools.
    """

    def __init__(self, inputs: dict[str, pd.DataFrame], anchors: tuple[str, ...]) -> None:
        self._inputs = inputs
        self._outputs: dict[str, pd.DataFrame] = {}
        self._anchor_names = anchors or ("#1",)

    def read(self, anchor: str = "#1") -> pd.DataFrame:
        key = anchor.lstrip("#") or "1"
        if key in self._inputs:
            return self._inputs[key].copy()
        if len(self._inputs) == 1:
            return next(iter(self._inputs.values())).copy()
        raise KeyError(f"Python tool has no incoming anchor {anchor!r}")

    def write(self, frame: pd.DataFrame, anchor: str = "#1") -> None:
        self._outputs[anchor.lstrip("#") or "1"] = frame

    def getIncomingAnchorNames(self) -> list[str]:
        return list(self._inputs)

    def getOutgoingAnchorNamesMap(self) -> dict[str, list[str]]:
        return {"#1": list(self._anchor_names)}


def _extract_notebook_code(notebook_text: str) -> str:
    """Extract concatenated code cells from a serialized Jupyter notebook."""
    if not notebook_text:
        return ""
    text = notebook_text.strip()
    if text.startswith("{"):
        try:
            notebook = json.loads(text)
        except json.JSONDecodeError:
            return ""
        cells = [
            "".join(cell.get("source", []))
            for cell in notebook.get("cells", [])
            if cell.get("cell_type") == "code"
        ]
        return "\n".join(cells)
    return text


def jupytercode_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    from alteryx2python.generator.python_tool import lower_python_script, saved_python_script
    from textwrap import indent

    script = saved_python_script(config)
    arguments = {anchor: f'_input_{index}' for index, anchor in enumerate(inputs)}
    constants = (context.runtime_config or {}).get('workflow_constants', {})
    body, anchors = lower_python_script(script, arguments, constants)
    source = 'def python_tool(' + ', '.join(arguments.values()) + '):
' + indent('
'.join(body), '    ')
    namespace = {}
    exec(compile(source, '<Python Tool>', 'exec'), namespace)
    result = namespace['python_tool'](*inputs.values())
    outputs = dict(zip(anchors, (result,) if len(anchors) == 1 else result or ()))
    context.record_node(
        node_id=str(config.get('node_id', 'unknown')),
        tool_type='JupyterCode', source_tool_id=config.get('source_tool_id'),
        inputs=inputs, outputs=outputs, status='success',
        config={'external_code_executed': True, 'venv_name': config.get('venv_name', ''),
                'script_length': len(script), 'output_anchors': list(anchors)},
    )
    return outputs


from __future__ import annotations

from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def runcommand_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    input_frame = inputs.get("Input")
    if input_frame is not None and not isinstance(input_frame, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")

    output = input_frame.copy() if isinstance(input_frame, pd.DataFrame) else pd.DataFrame()
    runtime = context.runtime_config or {}
    executed = False
    if runtime.get('execute_commands'):
        from alteryx2python.tools.delivery import run_checked_command
        from pathlib import Path
        base = Path(runtime.get('input_dir') or config.get('base_dir', '.'))
        directory = Path(config.get('working_dir') or base)
        if not directory.is_absolute():
            directory = base / directory
        program = str(config.get('program_name', ''))
        if not Path(program).is_absolute() and (base / program).is_file():
            program = str((base / program).resolve())
        output = run_checked_command(program, config.get('arguments', ''),
            runtime.get('command_working_dir') or directory,
            input_frame, config.get('input_file', ''), config.get('output_file', ''),
            runtime.get('allowed_commands', ()), runtime.get('command_timeout', 30))
        executed = True
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="RunCommand",
        source_tool_id=config.get("source_tool_id"),
        inputs={"Input": input_frame} if isinstance(input_frame, pd.DataFrame) else {},
        outputs=outputs,
        status="success",
        config={
            "program_name": config.get("program_name", ""),
            "arguments": config.get("arguments", ""),
            "working_dir": config.get("working_dir", ""),
            "input_file": config.get("input_file", ""),
            "output_file": config.get("output_file", ""),
            "external_command_executed": executed,
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


class RunCommandTool(BaseTool):
    tool_type = "RunCommand"
    input_anchors = ("Input",)
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return runcommand_tool(inputs, config, context)

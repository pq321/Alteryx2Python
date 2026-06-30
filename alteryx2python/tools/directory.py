from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from alteryx2python.comparison.schema_diff import snapshot_schema
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.tools.base_tool import BaseTool


def _resolve_directory(config: dict[str, Any]) -> Path:
    directory = Path(str(config.get("directory", ".")))
    if not directory.is_absolute():
        base_dir = Path(str(config.get("base_dir", ".")))
        directory = base_dir / directory
    return directory.resolve()


def directory_tool(
    inputs: dict[str, pd.DataFrame],
    config: dict[str, Any],
    context: WorkflowContext,
) -> dict[str, pd.DataFrame]:
    directory = _resolve_directory(config)
    if not directory.exists() or not directory.is_dir():
        raise FileNotFoundError(f"Directory tool path does not exist: {directory}")

    file_spec = str(config.get("file_spec", "*.*"))
    include_subdirs = bool(config.get("include_subdirs", False))
    iterator = directory.rglob(file_spec) if include_subdirs else directory.glob(file_spec)
    rows = []
    for path in sorted(iterator):
        if not path.is_file():
            continue
        stat = path.stat()
        rows.append(
            {
                "FullPath": str(path),
                "Directory": str(path.parent),
                "FileName": path.name,
                "ShortFileName": path.stem,
                "Extension": path.suffix,
                "Size": stat.st_size,
                "CreationTime": datetime_from_timestamp(stat.st_ctime),
                "LastAccessTime": datetime_from_timestamp(stat.st_atime),
                "LastWriteTime": datetime_from_timestamp(stat.st_mtime),
            }
        )
    output = pd.DataFrame(rows)
    outputs = {"Output": output}
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type="Directory",
        source_tool_id=config.get("source_tool_id"),
        inputs=inputs,
        outputs=outputs,
        status="success",
        config={
            "directory": str(directory),
            "file_spec": file_spec,
            "include_subdirs": include_subdirs,
            "output_schema": snapshot_schema(output),
        },
    )
    return outputs


def datetime_from_timestamp(value: float) -> str:
    return pd.Timestamp.fromtimestamp(value).isoformat()


class DirectoryTool(BaseTool):
    tool_type = "Directory"
    input_anchors = ()
    output_anchors = ("Output",)

    def execute(
        self,
        inputs: dict[str, pd.DataFrame],
        config: dict[str, Any],
        context: WorkflowContext,
    ) -> dict[str, pd.DataFrame]:
        return directory_tool(inputs, config, context)

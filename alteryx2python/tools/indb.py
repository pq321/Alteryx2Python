"""Local, deterministic implementations of the In-DB tool family.

These adapters deliberately execute against pandas (and sqlite for the two
database boundary tools).  They accept the normalized configuration emitted by
the XML parser as well as the small XML-shaped dictionaries used by Alteryx
sample workflows; no network/database-driver calls are made implicitly.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Callable
import pandas as pd

from alteryx2python.tools.base_tool import BaseTool
from alteryx2python.tools.filter import filter_tool
from alteryx2python.tools.formula import formula_tool
from alteryx2python.tools.join import join_tool
from alteryx2python.tools.sample import sample_tool
from alteryx2python.tools.select import select_tool
from alteryx2python.tools.summarize import summarize_tool
from alteryx2python.tools.transpose import transpose_tool
from alteryx2python.tools.union import union_tool


def _frame(inputs: dict[str, pd.DataFrame], anchor: str = "Input") -> pd.DataFrame:
    if anchor not in inputs:
        raise KeyError(f"In-DB tool requires a {anchor} input anchor")
    if not isinstance(inputs[anchor], pd.DataFrame):
        raise TypeError(f"{anchor} anchor must contain a pandas DataFrame")
    return inputs[anchor]


def _config(config: dict[str, Any], *names: str, default: Any = None) -> Any:
    for name in names:
        if name in config and config[name] not in (None, ""):
            return config[name]
    # Common XML parser shape: {Configuration: {…}}
    nested = config.get("Configuration") or config.get("configuration")
    if isinstance(nested, dict):
        return _config(nested, *names, default=default)
    return default


def _db_required(config: dict[str, Any]) -> str:
    value = _config(config, "connection", "Connection", "connection_string", "database")
    if not value:
        raise ValueError(
            "In-DB input/output requires an explicit sqlite connection/database"
        )
    value = str(value)
    if value != ":memory:" and not value.lower().endswith(
        (".db", ".sqlite", ".sqlite3")
    ):
        raise ValueError(
            "Only local sqlite databases are supported by the local In-DB adapter"
        )
    return value


def _input(inputs, config, context):
    db = _db_required(config)
    table = _config(config, "table", "Table", "query", "Query")
    if not table:
        raise ValueError("LockInInput requires table or query")
    with sqlite3.connect(db) as conn:
        query = str(table)
        if query.strip().lower().startswith("select"):
            out = pd.read_sql_query(query, conn)
        else:
            safe_table = '"' + query.replace('"', '""') + '"'
            out = pd.read_sql_query(f"SELECT * FROM {safe_table}", conn)
    return {"Output": out}


def _output(inputs, config, context):
    frame = _frame(inputs)
    db = _db_required(config)
    table = _config(config, "table", "Table", default="AlteryxOutput")
    with sqlite3.connect(db) as conn:
        frame.to_sql(
            str(table),
            conn,
            if_exists=str(_config(config, "if_exists", default="replace")),
            index=False,
        )
    return {"Output": frame.copy()}


def _sql_filter(inputs, config, context):
    frame = _frame(inputs)
    expression = str(config.get("sql_expression", "")).strip()
    if not expression:
        raise ValueError("LockInFilter requires expression or sql_expression")
    with sqlite3.connect(":memory:") as conn:
        work = frame.reset_index(drop=True).copy()
        key = "__a2p_position"
        while key in work.columns:
            key += "_"
        work[key] = range(len(work))
        work.to_sql("__input", conn, index=False)
        positions = pd.read_sql_query(
            f'SELECT "{key}" FROM __input WHERE {expression}', conn
        )[key].tolist()
    mask = pd.Series(False, index=range(len(frame)))
    mask.iloc[positions] = True
    return {
        "True": frame.iloc[mask.to_numpy()].copy(),
        "False": frame.iloc[(~mask).to_numpy()].copy(),
    }


def _identity(inputs, config, context):
    return {"Output": _frame(inputs).copy()}


def _record(context, tool_type, inputs, outputs, config):
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=tool_type,
        source_tool_id=config.get("source_tool_id"),
        inputs=inputs,
        outputs=outputs,
        status="success",
        config=dict(config),
    )


def _macro_input(inputs, config, context):
    return {
        "Output": _frame(inputs, str(_config(config, "anchor", default="Input"))).copy()
    }


def _macro_output(inputs, config, context):
    return {"Output": _frame(inputs).copy()}


_DELEGATES: dict[str, Callable] = {
    "LockInFilter": filter_tool,
    "LockInFormula": formula_tool,
    "LockInJoin": join_tool,
    "LockInSample": sample_tool,
    "LockInSelect": select_tool,
    "LockInSummarize": summarize_tool,
    "LockInUnion": union_tool,
    "LockInTranspose": transpose_tool,
}

_ANCHORS = {
    "LockInBrowse": (("Input",), ("Output",)),
    "LockInInput": ((), ("Output",)),
    "LockInStreamIn": ((), ("Output",)),
    "LockInStreamOut": (("Input",), ("Output",)),
    "LockInDynamicInput": ((), ("Output",)),
    "LockInDynamicOutput": (("Input",), ("Output",)),
    "LockInFilter": (("Input",), ("True", "False")),
    "LockInFormula": (("Input",), ("Output",)),
    "LockInJoin": (("Left", "Right"), ("Join", "Left", "Right")),
    "LockInMacroInput": (("Input",), ("Output",)),
    "LockInMacroOutput": (("Input",), ("Output",)),
    "LockInSample": (("Input",), ("Output",)),
    "LockInSelect": (("Input",), ("Output",)),
    "LockInSummarize": (("Input",), ("Output",)),
    "LockInUnion": (("Input",), ("Output",)),
    "LockInOutput": (("Input",), ("Output",)),
    "LockInTranspose": (("Input",), ("Output",)),
}


class _InDBTool(BaseTool):
    def execute(self, inputs, config, context):
        if self.tool_type in _DELEGATES:
            normalized = _normalize(self.tool_type, config)
            if self.tool_type == "LockInFilter" and normalized.get("sql_expression"):
                result = _sql_filter(inputs, normalized, context)
            else:
                result = _DELEGATES[self.tool_type](inputs, normalized, context)
        elif self.tool_type in {"LockInInput", "LockInDynamicInput"}:
            result = _input(inputs, config, context)
        elif self.tool_type in {"LockInStreamIn", "LockInStreamOut"}:
            result = _identity(inputs, config, context)
        elif self.tool_type in {"LockInOutput", "LockInDynamicOutput"}:
            result = _output(inputs, config, context)
        elif self.tool_type == "LockInMacroInput":
            result = _macro_input(inputs, config, context)
        elif self.tool_type == "LockInMacroOutput":
            result = _macro_output(inputs, config, context)
        else:
            result = _identity(inputs, config, context)
        if not context.traces or context.traces[-1].tool_type != self.tool_type:
            _record(context, self.tool_type, inputs, result, config)
        return result


def _normalize(tool_type: str, config: dict[str, Any]) -> dict[str, Any]:
    c = dict(config)
    nested = c.get("Configuration") or c.get("configuration")
    if isinstance(nested, dict):
        c = {**nested, **c}
    return c


def _make(name: str):
    return type(
        name,
        (_InDBTool,),
        {
            "tool_type": name,
            "input_anchors": _ANCHORS[name][0],
            "output_anchors": _ANCHORS[name][1],
        },
    )


IMPLEMENTATIONS = {name: _make(name) for name in _ANCHORS}
ANCHORS = _ANCHORS
PARSERS: dict[str, Any] = {}

# Parser adapters for native In-DB XML.  They intentionally preserve SQL
# expressions as SQL: a local pandas execution profile must opt in explicitly
# rather than accidentally evaluating database SQL as Alteryx formula syntax.
from alteryx2python.parser.tool_parsers.common import (
    ToolParserResult,
    as_list,
    attributes,
    text,
)


def _parse_common(raw: dict[str, Any]) -> ToolParserResult:
    c = raw.get("Configuration", raw)
    if not isinstance(c, dict):
        return ToolParserResult({})
    out: dict[str, Any] = {}
    for key, value in c.items():
        if key in {"Expression", "Query", "Sql", "SQL", "Connection", "Table"}:
            out[
                {
                    "Expression": "sql_expression",
                    "Query": "query",
                    "Sql": "sql_expression",
                    "SQL": "sql_expression",
                    "Connection": "connection",
                    "Table": "table",
                }.get(key, key)
            ] = text(value)
    sf = c.get("SelectFields")
    if sf is not None:
        fields = []
        for item in as_list(sf.get("Field", sf) if isinstance(sf, dict) else sf):
            a = attributes(item)
            name = a.get("field", a.get("name", text(item)))
            fields.append(
                {
                    "source": name,
                    "rename": a.get("rename", name),
                    "selected": str(a.get("selected", "True")).lower() != "false",
                }
            )
        out["select_fields"] = fields
    ji = c.get("JoinInfo")
    if ji is not None:
        joins = []
        for item in as_list(ji):
            a = attributes(item)
            if a:
                joins.append(
                    {
                        "connection": a.get("connection", a.get("side", "")),
                        "field": a.get("field", a.get("name", "")),
                    }
                )
        out["joins"] = joins
    return ToolParserResult(out)


PARSERS = {name: _parse_common for name in _ANCHORS}

# Integration consumes callables.  Keep classes available for callers that
# need introspection, while exposing the required (inputs, config, context)
# shape in IMPLEMENTATIONS.
TOOL_CLASSES = IMPLEMENTATIONS


def _call(cls):
    def execute(inputs, config, context):
        return cls().execute(inputs, config, context)

    execute.__name__ = cls.__name__ + "_execute"
    return execute


IMPLEMENTATIONS = {name: _call(cls) for name, cls in TOOL_CLASSES.items()}

"""Executable implementations for the small, local Alteryx macro family.

The functions intentionally accept the normalized configuration dictionaries used by
the runtime; unsupported modes raise ``ValueError`` instead of silently passing data.
"""

from __future__ import annotations

import base64, json
from typing import Any, Callable
import numpy as np
import pandas as pd
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.parser.tool_parsers.common import ToolParserResult


def _in(inputs):
    if not inputs:
        raise KeyError("macro requires an input anchor")
    return next(iter(inputs.values()))


def _done(name, inputs, out, config, context):
    context.record_node(
        node_id=str(config.get("node_id", "unknown")),
        tool_type=name,
        source_tool_id=config.get("source_tool_id"),
        inputs=inputs,
        outputs=out,
        status="success",
        config=config,
    )
    return out


def _field(c, default=None):
    return c.get("field", c.get("Field", c.get("FieldName", default)))


def count_records(inputs, config, context):
    frame = _in(inputs)
    out = {"Output9": pd.DataFrame({"Count": [len(frame)]})}
    return _done("CountRecords", inputs, out, config, context)


def weighted_avg(inputs, config, context):
    f = _in(inputs)
    value = config.get("Value", _field(config, "Value"))
    weight = config.get("weight", config.get("Weight"))
    if value not in f or weight not in f:
        raise KeyError("WeightedAvg requires value and weight fields")
    groups = config.get("GroupFields", config.get("group_fields", []))
    if isinstance(groups, str):
        import csv

        groups = next(csv.reader([groups])) if groups.strip() else []
    if any(field not in f for field in groups):
        raise KeyError("WeightedAvg group field is missing")
    output_name = config.get(
        "OutputFieldName", config.get("output_field", "WeightedAverage")
    )
    partitions = f.groupby(groups, dropna=False, sort=True) if groups else [((), f)]
    rows = []
    for key, frame in partitions:
        x = pd.to_numeric(frame[value], errors="raise")
        w = pd.to_numeric(frame[weight], errors="raise")
        valid = x.notna() & w.notna()
        denominator = w[valid].sum()
        average = (
            float((x[valid] * w[valid]).sum() / denominator)
            if denominator != 0
            else None
        )
        key = key if isinstance(key, tuple) else (key,)
        rows.append({**dict(zip(groups, key)), output_name: average})
    out = {"Output": pd.DataFrame(rows, columns=[*groups, output_name])}
    return _done("WeightedAvg", inputs, out, config, context)


def select_records(inputs, config, context):
    f = _in(inputs)
    start = int(config.get("start", config.get("StartRecord", 1)))
    end = config.get("end", config.get("EndRecord"))
    if "ranges" in config:
        mask = pd.Series(False, index=f.index)
        for lo, hi in config["ranges"]:
            mask.iloc[max(0, int(lo) - 1) : int(hi)] = True
        out = {"Output": f.loc[mask].copy()}
    else:
        end = len(f) if end in (None, "") else int(end)
        out = {"Output": f.iloc[max(0, start - 1) : end].copy()}
    return _done("SelectRecords", inputs, out, config, context)


def base64_encoder(inputs, config, context):
    f = _in(inputs).copy()
    src = config.get("source_field", _field(config))
    dst = config.get("output_field", config.get("OutputField", src + "_Base64"))
    if src not in f:
        raise KeyError(src)
    f[dst] = f[src].map(
        lambda x: None if pd.isna(x) else base64.b64encode(str(x).encode()).decode()
    )
    return _done("Base64Encoder", inputs, {"Output": f}, config, context)


def json_build(inputs, config, context):
    f = _in(inputs)
    name_field = config.get("name_field", config.get("NameField", "JSON_Name"))
    if name_field not in f:
        raise KeyError("JSONBuild requires the JSON Parse name/value table schema")
    groups = config.get("group_fields", config.get("GroupFields", []))
    if isinstance(groups, str):
        import csv

        groups = next(csv.reader([groups])) if groups.strip() else []
    if any(field not in f for field in groups):
        raise KeyError("JSONBuild grouping field missing")
    value_fields = []
    for kind, default in (
        ("string", "JSON_ValueString"),
        ("int", "JSON_ValueInt"),
        ("float", "JSON_ValueFloat"),
        ("bool", "JSON_ValueBool"),
    ):
        field = config.get(f"{kind}_field", default)
        if field in f:
            value_fields.append((kind, field))
    if not value_fields:
        raise ValueError("JSONBuild requires at least one value field")
    output_name = config.get("output_field", config.get("OutputFieldName", "JSON"))
    rows = []
    partitions = (
        f.groupby(groups, dropna=False, sort=False)
        if groups
        else ([] if f.empty else [((), f)])
    )
    for group, frame in partitions:
        root = None
        seen = set()
        for row in frame.to_dict("records"):
            path = str(row[name_field]).split(".")
            if tuple(path) in seen:
                raise ValueError(
                    "JSONBuild contains duplicate paths; configure grouping fields"
                )
            seen.add(tuple(path))
            value = None
            for kind, field in value_fields:
                item = row[field]
                if item is not None and not pd.isna(item):
                    value = {"int": int, "float": float, "bool": bool, "string": str}[
                        kind
                    ](item)
                    break
            if root is None:
                root = [] if path[0].isdigit() else {}
            cursor = root
            for index, segment in enumerate(path):
                last = index == len(path) - 1
                container = [] if not last and path[index + 1].isdigit() else {}
                if isinstance(cursor, list):
                    if not segment.isdigit():
                        raise ValueError(
                            "JSONBuild array path must contain numeric indexes"
                        )
                    number = int(segment)
                    while len(cursor) <= number:
                        cursor.append(None)
                    if last:
                        cursor[number] = value
                    else:
                        if cursor[number] is None:
                            cursor[number] = container
                        cursor = cursor[number]
                elif isinstance(cursor, dict):
                    if last:
                        cursor[segment] = value
                    else:
                        cursor = cursor.setdefault(segment, container)
                else:
                    raise ValueError("JSONBuild path conflicts with a scalar value")
        group = group if isinstance(group, tuple) else (group,)
        rows.append(
            {
                **dict(zip(groups, group)),
                output_name: json.dumps(
                    root or {}, ensure_ascii=False, separators=(",", ":")
                ),
            }
        )
    return _done(
        "JSONBuild",
        inputs,
        {"Output": pd.DataFrame(rows, columns=[*groups, output_name])},
        config,
        context,
    )


def spearman(inputs, config, context):
    f = _in(inputs)
    fields = config.get("fields", config.get("Fields"))
    if not fields or len(fields) < 2:
        raise ValueError("SpearmanCorrCoeff requires at least two fields")
    out = {"Output": f[list(fields)].corr(method="spearman")}
    return _done("SpearmanCorrCoeff", inputs, out, config, context)


def frequency(inputs, config, context):
    f = _in(inputs)
    field = _field(config)
    if field not in f:
        raise KeyError(field)
    out = {"Output": f.groupby(field, dropna=False).size().reset_index(name="Count")}
    return _done("FrequencyTable", inputs, out, config, context)


def contingency(inputs, config, context):
    f = _in(inputs)
    rows = config.get("row_field", config.get("RowField"))
    cols = config.get("column_field", config.get("ColumnField"))
    if rows not in f or cols not in f:
        raise KeyError("ContingencyTable fields missing")
    out = {"Output": pd.crosstab(f[rows], f[cols], dropna=False)}
    return _done("ContingencyTable", inputs, out, config, context)


def imputation(inputs, config, context):
    f = _in(inputs).copy()
    fields = config.get("fields", config.get("Fields", [config.get("field")]))
    method = config.get("method", config.get("Method", "mean")).lower()
    if method not in {"mean", "median", "mode", "constant"}:
        raise ValueError("unsupported Imputation method")
    for col in fields:
        if col not in f:
            raise KeyError(col)
        values = pd.to_numeric(f[col], errors="raise")
        mask = (
            values.isna()
            if config.get("replace_from", "null") == "null"
            else values.eq(float(config["replace_from"]))
        )
        source = values.loc[~mask]
        if method == "constant":
            fill = float(config.get("value", 0))
        elif source.empty:
            raise ValueError(
                "Imputation cannot estimate a replacement from an empty field"
            )
        else:
            fill = (
                source.mode(dropna=True).iloc[0]
                if method == "mode"
                else getattr(source, method)()
            )
        target = col + "_ImputedValue" if config.get("separate_field") else col
        f[target] = values.where(~mask, fill)
        if config.get("indicator"):
            f[col + "_Indicator"] = mask.astype("int8")
    return _done("Imputation", inputs, {"Output": f}, config, context)


def random_records(inputs, config, context):
    f = _in(inputs)
    n = config.get("number", config.get("N"))
    frac = config.get("percentage", config.get("Percent"))
    rng = np.random.default_rng(config.get("seed", config.get("Seed")))
    if n is None and frac is None:
        raise ValueError("RandomRecords requires number or percentage")
    take = int(round(len(f) * float(frac) / 100)) if n is None else int(n)
    if take < 0 or take > len(f):
        raise ValueError("RandomRecords count is outside input range")
    idx = (
        np.sort(rng.choice(len(f), take, replace=False))
        if take
        else np.array([], dtype=int)
    )
    selected = np.zeros(len(f), dtype=bool)
    selected[idx] = True
    return _done("RandomRecords", inputs, {"Output": f.iloc[idx]}, config, context)


def create_samples(inputs, config, context):
    f = _in(inputs)
    est = float(config.get("estimation pct", config.get("estimation_pct", 50)))
    val = float(config.get("validation pct", config.get("validation_pct", 50)))
    if est < 0 or val < 0 or est + val > 100:
        raise ValueError(
            "CreateSamples percentages must be non-negative and sum to at most 100"
        )
    rng = np.random.default_rng(int(config.get("rand seed", config.get("seed", 1))))
    order = rng.permutation(len(f))
    a = int(len(f) * est / 100)
    b = a + int(len(f) * val / 100)
    return _done(
        "CreateSamples",
        inputs,
        {
            "Estimation": f.iloc[order[:a]],
            "Validation": f.iloc[order[a:b]],
            "Holdout": f.iloc[order[b:]],
        },
        config,
        context,
    )


def multifield_binning(inputs, config, context):
    f = _in(inputs).copy()
    fields = config.get("fields", config.get("Fields", []))
    bins = int(config.get("bins", config.get("BinCount", 5)))
    for col in fields:
        if col not in f:
            raise KeyError(col)
        f[col + "_Bin"] = pd.qcut(f[col], q=bins, labels=False, duplicates="drop")
    return _done("MultiFieldBinning", inputs, {"Output": f}, config, context)


def oversample(inputs, config, context):
    f = _in(inputs)
    field = config.get("Selected_Field", _field(config))
    target = config.get("Oversample_Value", config.get("target", config.get("Target")))
    desired = float(
        config.get(
            "Desired_Pct", config.get("desired_pct", config.get("percentage", 50))
        )
    )
    if field not in f or target is None or not 0 < desired <= 100:
        raise ValueError(
            "OversampleField requires Selected_Field, Oversample_Value and Desired_Pct"
        )
    base = f[f[field] != target]
    chosen = f[f[field] == target]
    if chosen.empty:
        raise ValueError("Oversample value is absent")
    if desired == 100:
        need = len(base)
    else:
        need = max(
            0,
            int(
                np.ceil(
                    (desired * len(base) / 100 - (100 - desired) * len(chosen) / 100)
                    / (1 - desired / 100)
                )
            ),
        )
    rng = np.random.default_rng(config.get("seed"))
    extra = chosen.sample(need, replace=True, random_state=int(rng.integers(2**31)))
    out = pd.concat([f, extra], ignore_index=True)
    return _done("OversampleField", inputs, {"Output": out}, config, context)


def field_summary(inputs, config, context):
    f = _in(inputs)
    out = pd.DataFrame(
        {
            "Field": f.columns,
            "Count": [f[c].count() for c in f],
            "NullCount": [f[c].isna().sum() for c in f],
            "UniqueCount": [f[c].nunique(dropna=True) for c in f],
        }
    )
    return _done("FieldSummaryReport", inputs, {"Output": out}, config, context)


IMPLEMENTATIONS: dict[str, Callable] = {
    "CountRecords": count_records,
    "WeightedAvg": weighted_avg,
    "SelectRecords": select_records,
    "Base64Encoder": base64_encoder,
    "JSONBuild": json_build,
    "SpearmanCorrCoeff": spearman,
    "FrequencyTable": frequency,
    "ContingencyTable": contingency,
    "Imputation": imputation,
    "RandomRecords": random_records,
    "CreateSamples": create_samples,
    "MultiFieldBinning": multifield_binning,
    "OversampleField": oversample,
    "FieldSummaryReport": field_summary,
}
ANCHORS = {k: (("Input",), ("Output",)) for k in IMPLEMENTATIONS}
ANCHORS["CountRecords"] = (("Input8",), ("Output9",))


def _parse_values(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize parser output from XML ``Value name=...`` nodes."""
    values = raw.get("Value", raw.get("values", raw)) if isinstance(raw, dict) else {}
    if isinstance(values, dict):
        values = [values]
    result: dict[str, Any] = {}
    for item in values if isinstance(values, list) else []:
        if not isinstance(item, dict):
            continue
        attrs = item.get("attributes", item)
        name = attrs.get("name") if isinstance(attrs, dict) else None
        if not name:
            continue
        value = item.get("text", item.get("value", ""))
        result[str(name)] = value
    if result:
        if "estimation pct" in result:
            result["estimation_pct"] = float(result["estimation pct"])
        if "validation pct" in result:
            result["validation_pct"] = float(result["validation pct"])
        if "rand seed" in result:
            result["seed"] = int(result["rand seed"])
        if "listbox Select Incoming Fields" in result:
            import csv

            result["fields"] = next(
                csv.reader([str(result["listbox Select Incoming Fields"])])
            )
            truth = lambda key: str(result.get(key, "False")).lower() == "true"
            modes = [
                name for name in ("Mean", "Median", "Mode") if truth("radio " + name)
            ]
            result["method"] = modes[0].lower() if modes else "constant"
            result["value"] = result.get("updown User Replace With Value", 0)
            result["replace_from"] = (
                "null"
                if truth("radio Null Value")
                else result.get("updown User Replace Value", 0)
            )
            result["indicator"] = truth("checkbox Impute Indicator")
            result["separate_field"] = truth("checkbox Imputed Values Separate Field")
        if "Ranges" in result:
            ranges = []
            for line in str(result["Ranges"]).splitlines():
                line = line.strip()
                if not line:
                    continue
                if line.endswith("+"):
                    ranges.append((int(line[:-1]), 2**31 - 1))
                elif "-" in line:
                    lo, hi = line.split("-", 1)
                    ranges.append((int(lo) if lo else 1, int(hi)))
                else:
                    ranges.append((int(line), int(line)))
            result["ranges"] = ranges
        macro_input = result.get("Input.Macro Input", "")
        if "Text=" in str(macro_input):
            result["source_field"] = (
                str(macro_input).split("Text=", 1)[1].strip().splitlines()[0]
            )
    return ToolParserResult(normalized_config=result)


PARSERS = {name: _parse_values for name in IMPLEMENTATIONS}
